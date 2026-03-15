"""Notification routes: list, mark read, get/update preferences."""

from datetime import UTC, datetime

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationRead,
    PreferenceUpdate,
)
from app.models.user import User

router = APIRouter(tags=["notifications"])


@router.get("/api/notifications", response_model=list[NotificationRead])
async def list_notifications(
    user: User = Depends(get_current_user),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List the current user's notifications, newest first."""
    notifs = (
        await Notification.find(Notification.recipient_id == str(user.id))
        .sort("-created_at")
        .skip(offset)
        .limit(limit)
        .to_list()
    )
    return [NotificationRead.from_doc(n) for n in notifs]


@router.patch("/api/notifications/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: str,
    user: User = Depends(get_current_user),
):
    """Mark a single notification as read (no-op for now; prepares for in-app channel)."""
    try:
        notif = await Notification.get(PydanticObjectId(notification_id))
    except (InvalidId, ValueError):
        notif = None
    if notif is None or notif.recipient_id != str(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")


@router.get("/api/notifications/preferences")
async def get_preferences(user: User = Depends(get_current_user)):
    """Get the current user's notification preferences."""
    pref = await NotificationPreference.find_one(NotificationPreference.user_id == str(user.id))
    if pref is None:
        pref = NotificationPreference(user_id=str(user.id))
        await pref.insert()
    return {
        "user_id": str(user.id),
        "preferences": pref.preferences,
        "updated_at": pref.updated_at,
    }


@router.put("/api/notifications/preferences")
async def update_preferences(
    payload: PreferenceUpdate,
    user: User = Depends(get_current_user),
):
    """Update the current user's notification preferences."""
    pref = await NotificationPreference.find_one(NotificationPreference.user_id == str(user.id))
    if pref is None:
        pref = NotificationPreference(user_id=str(user.id), preferences=payload.preferences)
        await pref.insert()
    else:
        pref.preferences = payload.preferences
        pref.updated_at = datetime.now(UTC)
        await pref.save()
    return {
        "user_id": str(user.id),
        "preferences": pref.preferences,
        "updated_at": pref.updated_at,
    }
