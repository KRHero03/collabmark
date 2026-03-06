"""Comment routes: create, list, reply, resolve, reanchor, orphan, delete."""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.models.comment import CommentCreate, CommentRead, CommentReanchor, ReplyCreate
from app.models.user import User
from app.services import comment_service

router = APIRouter(tags=["comments"])


@router.post(
    "/api/documents/{doc_id}/comments",
    response_model=CommentRead,
    status_code=201,
)
async def create_comment(
    doc_id: str,
    payload: CommentCreate,
    user: User = Depends(get_current_user),
):
    """Create a comment on a document (inline or doc-level).

    Args:
        doc_id: Document ID.
        payload: Comment content, optional text anchor (absolute offsets,
                 Yjs RelativePositions, quoted text).
        user: Injected by get_current_user dependency.

    Returns:
        CommentRead of the created comment.
    """
    comment = await comment_service.create_comment(doc_id, user, payload)
    return CommentRead.from_doc(comment)


@router.get(
    "/api/documents/{doc_id}/comments",
    response_model=list[CommentRead],
)
async def list_comments(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """List all comments for a document, with replies nested.

    Args:
        doc_id: Document ID.
        user: Injected by get_current_user dependency.

    Returns:
        List of top-level CommentRead items with replies.
    """
    return await comment_service.list_comments(doc_id)


@router.post(
    "/api/comments/{comment_id}/reply",
    response_model=CommentRead,
    status_code=201,
)
async def reply_to_comment(
    comment_id: str,
    payload: ReplyCreate,
    user: User = Depends(get_current_user),
):
    """Reply to an existing comment (single-depth only).

    Args:
        comment_id: Parent comment ID.
        payload: Reply content.
        user: Injected by get_current_user dependency.

    Returns:
        CommentRead of the created reply.
    """
    reply = await comment_service.reply_to_comment(
        comment_id, user, payload.content
    )
    return CommentRead.from_doc(reply)


@router.post(
    "/api/comments/{comment_id}/resolve",
    response_model=CommentRead,
)
async def resolve_comment(
    comment_id: str,
    user: User = Depends(get_current_user),
):
    """Mark a comment as resolved.

    Args:
        comment_id: Comment ID.
        user: Injected by get_current_user dependency.

    Returns:
        CommentRead of the resolved comment.
    """
    comment = await comment_service.resolve_comment(comment_id, user)
    return CommentRead.from_doc(comment)


@router.patch(
    "/api/comments/{comment_id}/reanchor",
    response_model=CommentRead,
)
async def reanchor_comment(
    comment_id: str,
    payload: CommentReanchor,
    user: User = Depends(get_current_user),
):
    """Update a comment's absolute anchor positions after frontend re-resolution.

    Called by the frontend when Yjs RelativePositions resolve to new absolute
    character offsets that differ from the currently stored values.

    Args:
        comment_id: Comment ID.
        payload: New anchor_from and anchor_to offsets.
        user: Injected by get_current_user dependency.

    Returns:
        CommentRead of the updated comment.
    """
    comment = await comment_service.reanchor_comment(
        comment_id, payload.anchor_from, payload.anchor_to
    )
    return CommentRead.from_doc(comment)


@router.patch(
    "/api/comments/{comment_id}/orphan",
    response_model=CommentRead,
)
async def orphan_comment(
    comment_id: str,
    user: User = Depends(get_current_user),
):
    """Mark a comment as orphaned (its anchored text was deleted).

    The comment remains visible in the global comments panel but is no
    longer displayed inline.

    Args:
        comment_id: Comment ID.
        user: Injected by get_current_user dependency.

    Returns:
        CommentRead of the orphaned comment.
    """
    comment = await comment_service.orphan_comment(comment_id)
    return CommentRead.from_doc(comment)


@router.delete("/api/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    user: User = Depends(get_current_user),
):
    """Delete a comment. Author only. Deletes replies if top-level.

    Args:
        comment_id: Comment ID.
        user: Injected by get_current_user dependency.
    """
    await comment_service.delete_comment(comment_id, user)
