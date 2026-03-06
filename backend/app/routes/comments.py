"""Comment routes: create, list, reply, resolve, reanchor, orphan, delete.

All endpoints enforce document-level access: the caller must have at least
VIEW permission on the parent document before any comment operation.
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.models.comment import CommentCreate, CommentRead, CommentReanchor, ReplyCreate
from app.models.user import User
from app.services import comment_service, document_service

router = APIRouter(tags=["comments"])


async def _assert_doc_access_for_comment(comment_id: str, user: User) -> None:
    """Look up the comment's parent document and verify VIEW access."""
    comment = await comment_service._find_comment_or_404(comment_id)
    await document_service.get_document(comment.document_id, user)


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
    """Create a comment on a document. Requires VIEW access."""
    await document_service.get_document(doc_id, user)
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
    """List all comments for a document. Requires VIEW access."""
    await document_service.get_document(doc_id, user)
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
    """Reply to an existing comment. Requires VIEW access on the parent document."""
    await _assert_doc_access_for_comment(comment_id, user)
    reply = await comment_service.reply_to_comment(comment_id, user, payload.content)
    return CommentRead.from_doc(reply)


@router.post(
    "/api/comments/{comment_id}/resolve",
    response_model=CommentRead,
)
async def resolve_comment(
    comment_id: str,
    user: User = Depends(get_current_user),
):
    """Mark a comment as resolved. Requires VIEW access on the parent document."""
    await _assert_doc_access_for_comment(comment_id, user)
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
    """Update a comment's anchor positions. Requires VIEW access on the parent document."""
    await _assert_doc_access_for_comment(comment_id, user)
    comment = await comment_service.reanchor_comment(comment_id, payload.anchor_from, payload.anchor_to)
    return CommentRead.from_doc(comment)


@router.patch(
    "/api/comments/{comment_id}/orphan",
    response_model=CommentRead,
)
async def orphan_comment(
    comment_id: str,
    user: User = Depends(get_current_user),
):
    """Mark a comment as orphaned. Requires VIEW access on the parent document."""
    await _assert_doc_access_for_comment(comment_id, user)
    comment = await comment_service.orphan_comment(comment_id)
    return CommentRead.from_doc(comment)


@router.delete("/api/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    user: User = Depends(get_current_user),
):
    """Delete a comment. Author only + requires VIEW access on the parent document."""
    await _assert_doc_access_for_comment(comment_id, user)
    await comment_service.delete_comment(comment_id, user)
