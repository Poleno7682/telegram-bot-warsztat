"""Booking handlers - creating and managing bookings"""

from typing import Any, Awaitable, Callable, cast
from aiogram import Bot, Router, F
from aiogram.types import Message as TelegramMessage, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.dto import ServiceCreateData
from app.models.user import User, UserRole, LANGUAGE_UNSET
from app.core.timezone_utils import ensure_local
from app.services.booking_service import BookingService
from app.services.booking_workflow_service import BookingWorkflowService
from app.services.time_service import TimeService
from app.services.service_management_service import ServiceManagementService
from app.services.translation_service import translate_to_all_languages
from app.bot.states.booking import BookingStates
from app.utils.date_formatter import DateFormatter
from app.utils.validators import validate_phone
from app.utils.callback_utils import parse_callback_data
from app.utils.booking_utils import format_booking_details, format_booking_status
from app.bot.keyboards.inline import (
    get_services_keyboard,
    get_dates_keyboard,
    get_times_keyboard,
    get_cancel_keyboard,
    get_skip_keyboard
)
from app.bot.handlers.common import safe_callback_answer, schedule_main_menu_return, _build_menu_payload, edit_or_ignore

router = Router(name="booking")

# client_phone is NOT NULL in the DB (unlike description, which is stored
# as an empty string when skipped and has a display-time fallback in
# format_booking_details) and is shown in several places (notifications,
# calendar, mechanic's booking list) without a shared getter to hang a
# fallback off of - so skipping it stores this neutral placeholder
# directly instead of an empty string.
NO_PHONE_PLACEHOLDER = "-"


@router.callback_query(F.data == "menu:new_booking")
async def start_new_booking(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext,
    language: str
):
    """Start new booking flow"""
    from app.bot.handlers.common import send_clean_menu

    if user.role == UserRole.MECHANIC:
        # Mechanics skip the fixed service catalog entirely and type the
        # service (or a freeform list of services) and its duration by
        # hand instead - see custom_service_name_entered/
        # custom_duration_entered below for the rest of this path.
        await send_clean_menu(
            callback=callback,
            text=_("booking.create.enter_custom_service"),
            reply_markup=get_cancel_keyboard(_)
        )
        await state.set_state(BookingStates.entering_custom_service_name)
        await safe_callback_answer(callback)
        return

    # Get all active services
    service_mgmt = ServiceManagementService(session)
    services = await service_mgmt.get_all_active_services()

    if not services:
        await send_clean_menu(
            callback=callback,
            text=_("service_management.no_services"),
            reply_markup=get_cancel_keyboard(_)
        )
        await safe_callback_answer(callback)
        return

    # Show services with clean menu
    await send_clean_menu(
        callback=callback,
        text=_("booking.create.select_service"),
        reply_markup=get_services_keyboard(services, language, _)
    )
    await state.set_state(BookingStates.selecting_service)
    await safe_callback_answer(callback)


@router.callback_query(BookingStates.selecting_service, F.data.startswith("service:"))
async def service_selected(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext,
    language: str
):
    """Handle service selection"""
    service_id = parse_callback_data(callback.data, "service:", index=1)
    if service_id is None:
        await safe_callback_answer(callback)
        return

    # Get service to get duration
    service_mgmt = ServiceManagementService(session)
    service = await service_mgmt.get_service_by_id(service_id)

    if not service:
        await edit_or_ignore(callback, _("errors.service_not_found"))
        await state.clear()
        await safe_callback_answer(callback)
        return

    await _advance_to_date_selection(
        session=session,
        state=state,
        language=language,
        _=_,
        send_result=lambda text, **kw: edit_or_ignore(callback, text, **kw),
        service_id=service_id,
        duration_minutes=service.duration_minutes,
    )
    await safe_callback_answer(callback)


async def _advance_to_date_selection(
    *,
    session: AsyncSession,
    state: FSMContext,
    language: str,
    _: Callable[[str], str],
    send_result: Callable[..., Awaitable[Any]],
    service_id: int,
    duration_minutes: int,
) -> None:
    """Shared tail once a service and its duration are known - regardless
    of whether the service came from the fixed catalog (service_selected)
    or was typed by a mechanic (custom_duration_entered): look up
    available dates and move on to date selection.

    Args:
        send_result: Shows the next prompt (or the "no dates" error) -
            edit_or_ignore for the catalog-picking flow (callback-driven),
            message.answer for the mechanic's free-text flow.
    """
    await state.update_data(service_id=service_id)

    time_service = TimeService(session)
    dates = await time_service.get_available_dates(duration_minutes)

    if not dates:
        await send_result(_("booking.create.no_available_dates"))
        return

    await send_result(
        _("booking.create.select_date"),
        reply_markup=get_dates_keyboard(dates, language)
    )
    await state.set_state(BookingStates.selecting_date)


@router.message(BookingStates.entering_custom_service_name)
async def custom_service_name_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle a mechanic's freeform service name/list input."""
    if not message.text or not message.text.strip():
        await message.answer(_("errors.invalid_input"))
        return

    await state.update_data(custom_service_name=message.text.strip())
    await message.answer(
        _("booking.create.enter_custom_duration"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(BookingStates.entering_custom_duration)


@router.message(BookingStates.entering_custom_duration)
async def custom_duration_entered(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext,
    language: str,
):
    """Handle a mechanic's manually entered service duration.

    Creates a one-off Service row for the typed name (auto-translated,
    same as the booking description elsewhere in this flow - no
    translation-confirmation step, unlike the admin "add service" flow,
    since this one is just a means to get a valid service_id for this
    single booking). Created active - BookingService.create_booking
    rejects service.is_active=False outright, so it must stay active
    until the booking actually exists; it's marked is_custom_service in
    FSM state and deactivated in _create_booking_and_respond right after
    the booking is created, so it doesn't linger in the regular
    catalog/picker for everyone else. Then joins the standard flow via
    _advance_to_date_selection, same as picking a real service does.
    """
    if not message.text:
        await message.answer(_("errors.invalid_input"))
        return

    try:
        duration = int(message.text.strip())
        if duration <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(_("errors.invalid_input"))
        return

    data = await state.get_data()
    service_name = (data.get("custom_service_name") or "").strip()
    if not service_name:
        await message.answer(_("errors.unknown"))
        await state.clear()
        return

    translations = await translate_to_all_languages(service_name, source_lang=language)

    service_mgmt = ServiceManagementService(session)
    service = await service_mgmt.create_service(
        ServiceCreateData(
            name_pl=translations.get("pl", service_name),
            name_ru=translations.get("ru", service_name),
            duration_minutes=duration,
        )
    )
    await state.update_data(is_custom_service=True)

    await _advance_to_date_selection(
        session=session,
        state=state,
        language=language,
        _=_,
        send_result=lambda text, **kw: message.answer(text, **kw),
        service_id=service.id,
        duration_minutes=duration,
    )


@router.callback_query(BookingStates.selecting_date, F.data.startswith("date:"))
async def date_selected(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext,
    language: str
):
    """Handle date selection"""
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    if not callback.data or not callback.data.startswith("date:"):
        await safe_callback_answer(callback)
        return
    date_str = callback.data.split(":")[1]
    target_date = datetime.fromisoformat(date_str).date()
    
    # Get data
    data = await state.get_data()
    service_id = data.get("service_id")
    
    if not service_id or not isinstance(service_id, int):
        await edit_or_ignore(callback, _("errors.unknown"))
        await state.clear()
        await safe_callback_answer(callback)
        return
    
    # Get service
    service_mgmt = ServiceManagementService(session)
    service = await service_mgmt.get_service_by_id(service_id)
    
    if not service:
        await edit_or_ignore(callback, _("errors.service_not_found"))
        await state.clear()
        await safe_callback_answer(callback)
        return
    
    # Calculate available time slots
    time_service = TimeService(session)
    available_times = await time_service.calculate_available_slots(
        target_date,
        service.duration_minutes
    )
    
    if not available_times:
        await edit_or_ignore(callback, _("booking.create.no_available_slots"))
        await safe_callback_answer(callback)
        return
    
    # Save date
    await state.update_data(booking_date=date_str)

    # Show times
    await edit_or_ignore(
        callback,
        _("booking.create.select_time"),
        reply_markup=get_times_keyboard(available_times, language, _)
    )
    await state.set_state(BookingStates.selecting_time)
    await safe_callback_answer(callback)


async def _handle_time_change_proposal(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext,
    booking_id: int,
    new_datetime: datetime,
) -> None:
    """Handle a mechanic or creator proposing a new time for an existing
    booking (the "change time" flow entered from booking:change_time:/
    booking:user_propose_time: and completed here once a new slot is picked).

    Delegates the state transition + notification to BookingWorkflowService
    so this handler only deals with Telegram-facing concerns (who is
    allowed to propose, what message to show).
    """
    booking_service = BookingService(session)
    booking = await booking_service.get_booking_details(booking_id)

    if not booking:
        await edit_or_ignore(callback, _("errors.unknown"))
        await state.clear()
        await safe_callback_answer(callback)
        return

    is_mechanic = user.role == UserRole.MECHANIC
    is_creator = booking.creator_id == user.id

    if not is_mechanic and not is_creator:
        await edit_or_ignore(callback, _("errors.permission_denied"))
        await state.clear()
        await safe_callback_answer(callback)
        return

    workflow = BookingWorkflowService(session, callback.bot)
    booking, msg = await workflow.propose_time_and_notify(
        booking_id=booking_id,
        proposer_telegram_id=user.telegram_id,
        is_mechanic=is_mechanic,
        new_datetime=new_datetime,
    )

    if booking:
        confirmation_key = (
            "booking.actions.change_time" if is_mechanic else "booking.actions.propose_new_time"
        )
        await edit_or_ignore(callback, _(confirmation_key) + ": " + _("booking.confirm.time_proposed"))
        if callback.bot and isinstance(callback.message, TelegramMessage):
            schedule_main_menu_return(callback.bot, callback.message.chat.id, user)
    else:
        await edit_or_ignore(callback, _("errors.unknown") + f"\n{msg}")

    await state.clear()
    await safe_callback_answer(callback)


@router.callback_query(BookingStates.selecting_time, F.data.startswith("time:"))
async def time_selected(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle time selection"""
    if not callback.data:
        await safe_callback_answer(callback)
        return

    if not callback.data or not callback.data.startswith("time:"):
        await safe_callback_answer(callback)
        return
    # Extract time string after "time:" prefix (use split with maxsplit=1 to preserve colons in ISO format)
    time_str = callback.data.split(":", 1)[1]
    booking_datetime = datetime.fromisoformat(time_str)

    # Ensure booking_datetime is timezone-aware and in local timezone
    # Store time in local timezone (not UTC) as requested
    booking_datetime = ensure_local(booking_datetime)

    # Get data from state
    data = await state.get_data()
    change_time_booking_id = data.get("change_time_booking_id")

    # Check if this is time change flow
    if change_time_booking_id:
        await _handle_time_change_proposal(
            callback, session, user, _, state, change_time_booking_id, booking_datetime
        )
        return

    # Normal booking creation flow
    # Save time
    await state.update_data(booking_time=time_str)
    
    # Ask for car brand and model together
    await edit_or_ignore(
        callback,
        _("booking.create.enter_car_brand_model"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(BookingStates.entering_car_brand_model)
    await safe_callback_answer(callback)


@router.message(BookingStates.entering_car_brand_model)
async def car_brand_model_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle car brand and model input"""
    if not message.text:
        await message.answer(
            _("errors.invalid_input"),
            reply_markup=get_cancel_keyboard(_)
        )
        return
    
    # Parse brand and model from input
    # Try to split by common separators or use first word as brand, rest as model
    text = message.text.strip()
    
    # Try splitting by comma, dash, or space
    if ',' in text:
        parts = [p.strip() for p in text.split(',', 1)]
    elif ' - ' in text:
        parts = [p.strip() for p in text.split(' - ', 1)]
    elif ' — ' in text:
        parts = [p.strip() for p in text.split(' — ', 1)]
    elif '-' in text and not text.startswith('-'):
        parts = [p.strip() for p in text.split('-', 1)]
    else:
        # Split by first space
        parts = text.split(' ', 1)
    
    if len(parts) >= 2:
        car_brand = parts[0]
        car_model = parts[1]
    else:
        # If only one word, use it as brand, model is empty
        car_brand = parts[0] if parts else text
        car_model = ""
    
    await state.update_data(car_brand=car_brand, car_model=car_model)
    await message.answer(
        _("booking.create.enter_car_number"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(BookingStates.entering_car_number)


@router.message(BookingStates.entering_car_number)
async def car_number_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle car number input"""
    await state.update_data(car_number=message.text)
    await message.answer(
        _("booking.create.enter_client_name"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(BookingStates.entering_client_name)


@router.message(BookingStates.entering_client_name)
async def client_name_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle client name input"""
    await state.update_data(client_name=message.text)
    await message.answer(
        _("booking.create.enter_client_phone"),
        reply_markup=get_skip_keyboard(_, "booking:skip_phone")
    )
    await state.set_state(BookingStates.entering_client_phone)


@router.callback_query(F.data == "booking:skip_phone", BookingStates.entering_client_phone)
async def skip_client_phone(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Handle skipping the client phone number - same pattern as
    skip_description below, reused via the parameterized get_skip_keyboard."""
    if not isinstance(callback.message, TelegramMessage):
        await safe_callback_answer(callback)
        return

    await state.update_data(client_phone=NO_PHONE_PLACEHOLDER)
    await callback.message.edit_text(
        _("booking.create.enter_description"),
        reply_markup=get_skip_keyboard(_)
    )
    await state.set_state(BookingStates.entering_description)
    await safe_callback_answer(callback)


@router.message(BookingStates.entering_client_phone)
async def client_phone_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle client phone input"""
    # Validate phone number - only digits
    if not message.text:
        await message.answer(
            _("booking.create.phone_invalid"),
            reply_markup=get_skip_keyboard(_, "booking:skip_phone")
        )
        return

    # Validate phone number
    is_valid, phone = validate_phone(message.text)
    if not is_valid:
        await message.answer(
            _("booking.create.phone_invalid"),
            reply_markup=get_skip_keyboard(_, "booking:skip_phone")
        )
        return

    await state.update_data(client_phone=phone)
    await message.answer(
        _("booking.create.enter_description"),
        reply_markup=get_skip_keyboard(_)
    )
    await state.set_state(BookingStates.entering_description)


async def _create_booking_and_respond(
    *,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    description: str,
    bot: Bot | None,
    _: Callable[[str], str],
    language: str,
    send_translating_message: Callable[[], Awaitable[TelegramMessage]],
    show_result: Callable[[str], Awaitable[Any]],
    answer: Callable[[str], Awaitable[Any]],
    chat_id: int,
) -> None:
    """Shared tail of the booking-creation flow, used by both
    skip_description and description_entered (they used to duplicate this
    ~90-line block almost verbatim - see docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md,
    item 2.1). Resolves service_id from FSM state, creates the booking via
    BookingWorkflowService (which also notifies mechanics on success), then
    reports the result through the given responders.

    Args:
        show_result: Shows the booking details (success) or the error
            message (failure) - edit_text for the callback flow, answer for
            the plain-message flow.
        answer: Sends a plain follow-up message (always .answer(), never
            edit) - used for the "booking created" confirmation text.
    """
    data = await state.get_data()
    service_id = data.get("service_id")

    if not service_id:
        await show_result(_("errors.unknown"))
        await state.clear()
        return

    trans_msg = await send_translating_message()

    booking_datetime = ensure_local(datetime.fromisoformat(data["booking_time"]))
    workflow = BookingWorkflowService(session, bot)
    booking, msg = await workflow.create_booking_and_notify(
        creator_telegram_id=user.telegram_id,
        service_id=service_id,
        car_brand=data["car_brand"],
        car_model=data["car_model"],
        car_number=data["car_number"],
        client_name=data["client_name"],
        client_phone=data["client_phone"],
        description=description,
        language=language,
        booking_datetime=booking_datetime,
    )

    await trans_msg.delete()

    if booking:
        if data.get("is_custom_service"):
            # The service behind this booking was a one-off row typed by a
            # mechanic (see custom_duration_entered) - deactivate it now
            # that it has done its job, so it doesn't linger in the
            # regular catalog/admin service list. Must happen *after*
            # create_booking_and_notify succeeds, never before: it checks
            # service.is_active and would reject the booking outright if
            # the service were already inactive at creation time (see
            # BookingService.create_booking).
            await ServiceManagementService(session).delete_service(service_id)

        details = format_booking_details(booking, language, _)
        await show_result(details)
        await answer(_("booking.confirm.success"))
        schedule_main_menu_return(bot, chat_id, user)
    else:
        await show_result(_("booking.confirm.error") + f"\n{msg}")

    await state.clear()


@router.callback_query(F.data == "booking:skip_description", BookingStates.entering_description)
async def skip_description(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext,
    language: str
):
    """Handle skipping description"""
    if not isinstance(callback.message, TelegramMessage):
        await safe_callback_answer(callback)
        return

    message = callback.message
    await _create_booking_and_respond(
        session=session,
        user=user,
        state=state,
        description="",
        bot=callback.bot,
        _=_,
        language=language,
        send_translating_message=lambda: message.answer(_("booking.create.translating")),
        show_result=message.edit_text,
        answer=message.answer,
        chat_id=message.chat.id,
    )
    await safe_callback_answer(callback)


@router.message(BookingStates.entering_description)
async def description_entered(
    message: TelegramMessage,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext,
    language: str
):
    """Handle description input and create booking"""
    # Description is optional, so empty text is allowed
    description = message.text if message.text else ""

    await _create_booking_and_respond(
        session=session,
        user=user,
        state=state,
        description=description,
        bot=message.bot,
        _=_,
        language=language,
        send_translating_message=lambda: message.answer(_("booking.create.translating")),
        show_result=message.answer,
        answer=message.answer,
        chat_id=message.chat.id,
    )


@router.callback_query(F.data.startswith("booking:user_propose_time:"))
async def user_propose_time(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext,
    language: str
):
    """Handle user proposing new time for booking"""
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    booking_id = int(callback.data.split(":")[2])

    # Get booking to get service duration (with relations loaded)
    booking_service = BookingService(session)
    booking = await booking_service.get_booking_details(booking_id)

    if not booking or not booking.service:
        await edit_or_ignore(callback, _("errors.unknown"))
        await safe_callback_answer(callback)
        return
    
    # Verify user is the creator
    if booking.creator_id != user.id:
        await edit_or_ignore(callback, _("errors.permission_denied"))
        await safe_callback_answer(callback)
        return
    
    # Save booking_id and service_id to state for time change flow
    await state.update_data(
        change_time_booking_id=booking_id,
        service_id=booking.service_id
    )
    
    # Get available dates (filtered by available slots)
    time_service = TimeService(session)
    dates = await time_service.get_available_dates(booking.service.duration_minutes)
    
    # Check if there are any available dates
    if not dates:
        await edit_or_ignore(callback, _("booking.create.no_available_dates"))
        await safe_callback_answer(callback)
        return

    # Show dates
    await edit_or_ignore(
        callback,
        _("booking.create.select_date"),
        reply_markup=get_dates_keyboard(dates, language)
    )
    await state.set_state(BookingStates.selecting_date)
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("booking:confirm:"))
async def confirm_proposed_time(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Handle time confirmation by creator"""
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    booking_id = parse_callback_data(callback.data, "booking:confirm:", index=2)
    if booking_id is None:
        await safe_callback_answer(callback)
        return
    
    # Confirm time and notify the mechanic in one step
    workflow = BookingWorkflowService(session, callback.bot)
    booking, msg = await workflow.confirm_time_and_notify(
        booking_id=booking_id, creator_telegram_id=user.telegram_id
    )

    if booking:
        await edit_or_ignore(callback, _("booking.confirm.success"))

        # Return to main menu
        if callback.bot and isinstance(callback.message, TelegramMessage):
            schedule_main_menu_return(callback.bot, callback.message.chat.id, user)
    else:
        await edit_or_ignore(callback, _("errors.unknown") + f"\n{msg}")

    await safe_callback_answer(callback)


@router.callback_query(F.data == "booking:cancel")
async def cancel_booking_callback(
    callback: CallbackQuery,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle booking cancellation from callback - clear state and return to main menu"""
    # Clear FSM state
    await state.clear()
    
    # Return to main menu
    menu_text, keyboard = _build_menu_payload(user)
    await edit_or_ignore(
        callback,
        _("booking.create.booking_cancelled") + "\n\n" + menu_text,
        reply_markup=keyboard
    )

    await safe_callback_answer(callback)


# Note: Cancel button is available via callback_query handler above
# Users can click the cancel button on any step to cancel booking creation


@router.callback_query(F.data == "menu:my_bookings")
async def show_my_bookings(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    language: str
):
    """Show user's bookings"""
    from app.models.booking import BookingStatus

    booking_service = BookingService(session)
    bookings = await booking_service.get_user_bookings(user.telegram_id)

    if not bookings:
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(
                text=_("common.back"),
                callback_data="menu:main"
            )
        )
        await edit_or_ignore(
            callback,
            _("booking.my_bookings.no_bookings"),
            reply_markup=cast(InlineKeyboardMarkup, keyboard.as_markup())
        )
        await safe_callback_answer(callback)
        return
    
    # Format bookings list
    text = _("booking.my_bookings.title") + "\n\n"

    keyboard = InlineKeyboardBuilder()

    for booking in bookings:
        status_text = format_booking_status(booking.status, _)

        text += f"{status_text} — {DateFormatter.format_date(booking.booking_date, language)} "
        text += f"{DateFormatter.format_time(booking.booking_date)}\n"
        text += f"   🛠️ {booking.service.get_name(language)}\n"
        text += f"   🚗 {booking.car_brand} {booking.car_model}\n"
        if booking.status == BookingStatus.ACCEPTED and booking.mechanic:
            text += f"   🔧 {booking.mechanic.get_display_name()}\n"
        text += "\n"

        if booking.status in BookingService.ACTIVE_STATUSES:
            keyboard.row(
                InlineKeyboardButton(
                    text=f"{_('booking.actions.cancel_booking')} "
                         f"{DateFormatter.format_date(booking.booking_date, language)} "
                         f"{DateFormatter.format_time(booking.booking_date)}",
                    callback_data=f"booking:cancel_ask:{booking.id}"
                )
            )

    keyboard.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:main"
        )
    )
    await edit_or_ignore(
        callback,
        text,
        reply_markup=cast(InlineKeyboardMarkup, keyboard.as_markup())
    )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("booking:cancel_ask:"))
async def cancel_booking_ask(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    language: str
):
    """Ask for confirmation before cancelling an active booking."""
    if not callback.data:
        await safe_callback_answer(callback)
        return

    booking_id = parse_callback_data(callback.data, "booking:cancel_ask:", index=2)
    if booking_id is None:
        await safe_callback_answer(callback)
        return

    booking_service = BookingService(session)
    booking = await booking_service.get_booking_details(booking_id)
    if not booking:
        await safe_callback_answer(callback)
        return

    details_text = format_booking_details(booking, language, _)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text=_("common.yes"), callback_data=f"booking:cancel_do:{booking_id}"),
        # "menu:main" rather than "menu:my_bookings": this confirmation is
        # shared by both the creator's and the mechanic's booking lists, and
        # "main menu" is the one back-target valid for either.
        InlineKeyboardButton(text=_("common.no"), callback_data="menu:main"),
    )
    await edit_or_ignore(
        callback,
        _("booking.cancel.confirm_prompt").format(details=details_text),
        reply_markup=cast(InlineKeyboardMarkup, keyboard.as_markup())
    )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("booking:cancel_do:"))
async def cancel_booking_confirmed(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Execute a booking cancellation after the user confirmed it."""
    if not callback.data:
        await safe_callback_answer(callback)
        return

    booking_id = parse_callback_data(callback.data, "booking:cancel_do:", index=2)
    if booking_id is None:
        await safe_callback_answer(callback)
        return

    workflow = BookingWorkflowService(session, callback.bot)
    booking, msg = await workflow.cancel_booking_and_notify(
        booking_id=booking_id, actor_telegram_id=user.telegram_id
    )

    if booking:
        await edit_or_ignore(callback, _("booking.cancel.success"))
        if callback.bot and isinstance(callback.message, TelegramMessage):
            schedule_main_menu_return(callback.bot, callback.message.chat.id, user)
    else:
        await edit_or_ignore(callback, _("booking.cancel.error") + f"\n{msg}")

    await safe_callback_answer(callback)

