"""Comment business logic: create, reply, list, resolve, delete, reanchor, orphan."""

import logging

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.models.comment import Comment, CommentCreate, CommentRead
from app.models.user import User

logger = logging.getLogger(__name__)


async def create_comment(
    doc_id: str, user: User, payload: CommentCreate
) -> Comment:
    """Create a new comment (inline or doc-level) on a document.

    Args:
        doc_id: The document ID.
        user: The comment author.
        payload: Content, optional anchor positions (absolute + relative), and
                 quoted text.

    Returns:
        The created Comment.
    """
    comment = Comment(
        document_id=doc_id,
        author_id=str(user.id),
        author_name=user.name,
        author_avatar_url=user.avatar_url,
        content=payload.content,
        anchor_from=payload.anchor_from,
        anchor_to=payload.anchor_to,
        anchor_from_relative=payload.anchor_from_relative,
        anchor_to_relative=payload.anchor_to_relative,
        quoted_text=payload.quoted_text,
    )
    await comment.insert()
    return comment


async def reply_to_comment(
    comment_id: str, user: User, content: str
) -> Comment:
    """Reply to an existing comment (single-depth only).

    Args:
        comment_id: The parent comment ID.
        user: The reply author.
        content: The reply text.

    Returns:
        The created reply Comment.

    Raises:
        HTTPException: 404 if parent not found, 400 if replying to a reply.
    """
    parent = await _find_comment_or_404(comment_id)

    if parent.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reply to a reply (single-depth only)",
        )

    reply = Comment(
        document_id=parent.document_id,
        author_id=str(user.id),
        author_name=user.name,
        author_avatar_url=user.avatar_url,
        content=content,
        parent_id=str(parent.id),
    )
    await reply.insert()
    return reply


async def list_comments(doc_id: str) -> list[CommentRead]:
    """List all comments for a document, with replies nested under parents.

    Args:
        doc_id: The document ID.

    Returns:
        List of top-level CommentRead items with replies populated.
        Orphaned comments are included (frontend filters by is_orphaned).
    """
    all_comments = await Comment.find(
        Comment.document_id == doc_id,
    ).sort("created_at").to_list()

    top_level = []
    replies_map: dict[str, list[CommentRead]] = {}

    for c in all_comments:
        if c.parent_id:
            replies_map.setdefault(c.parent_id, []).append(
                CommentRead.from_doc(c)
            )
        else:
            top_level.append(c)

    return [
        CommentRead.from_doc(c, replies=replies_map.get(str(c.id), []))
        for c in top_level
    ]


async def resolve_comment(comment_id: str, user: User) -> Comment:
    """Mark a comment as resolved.

    Args:
        comment_id: The comment ID to resolve.
        user: The user resolving the comment.

    Returns:
        The resolved Comment.

    Raises:
        HTTPException: 404 if comment not found.
    """
    comment = await _find_comment_or_404(comment_id)
    comment.resolve(str(user.id))
    await comment.save()
    return comment


async def reanchor_comment(
    comment_id: str, anchor_from: int, anchor_to: int
) -> Comment:
    """Update a comment's absolute anchor offsets after frontend re-resolution.

    Called by the frontend when Yjs RelativePositions are resolved to new
    absolute positions that differ from the stored values.

    Args:
        comment_id: The comment ID to reanchor.
        anchor_from: New start character offset.
        anchor_to: New end character offset.

    Returns:
        The updated Comment.

    Raises:
        HTTPException: 404 if comment not found, 400 if not an inline comment.
    """
    comment = await _find_comment_or_404(comment_id)

    if comment.anchor_from is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reanchor a document-level comment",
        )

    comment.reanchor(anchor_from, anchor_to)
    await comment.save()
    return comment


async def orphan_comment(comment_id: str) -> Comment:
    """Mark a comment as orphaned (its anchored text was deleted).

    The comment remains visible in the global comments panel but is no
    longer displayed inline in the editor.

    Args:
        comment_id: The comment ID to orphan.

    Returns:
        The orphaned Comment.

    Raises:
        HTTPException: 404 if comment not found, 400 if already orphaned.
    """
    comment = await _find_comment_or_404(comment_id)

    if comment.is_orphaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment is already orphaned",
        )

    comment.orphan()
    await comment.save()
    return comment


async def delete_comment(comment_id: str, user: User) -> None:
    """Delete a comment. Only the author can delete their own comment.

    Also deletes all replies to this comment if it's a top-level comment.

    Args:
        comment_id: The comment ID to delete.
        user: The requesting user (must be author).

    Raises:
        HTTPException: 404 if not found, 403 if not author.
    """
    comment = await _find_comment_or_404(comment_id)

    if comment.author_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the comment author can delete this comment",
        )

    if comment.parent_id is None:
        await Comment.find(Comment.parent_id == str(comment.id)).delete()

    await comment.delete()


async def _find_comment_or_404(comment_id: str) -> Comment:
    """Fetch a comment by ID or raise 404.

    Only catches InvalidId/ValueError from malformed ObjectId strings.
    """
    try:
        comment = await Comment.get(PydanticObjectId(comment_id))
    except (InvalidId, ValueError):
        comment = None
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    return comment
