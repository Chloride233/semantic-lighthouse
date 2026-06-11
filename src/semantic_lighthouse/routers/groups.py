from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import get_current_user, get_membership_or_404, require_group_role
from semantic_lighthouse.models import (
    Group,
    GroupInvite,
    GroupJoinRequest,
    GroupMembership,
    User,
    as_utc,
    utc_now,
)
from semantic_lighthouse.schemas import (
    GroupCreateRequest,
    GroupResponse,
    InviteResponse,
    JoinByInviteRequest,
    JoinRequestResponse,
    MembershipResponse,
    RoleUpdateRequest,
)
from semantic_lighthouse.security import generate_refresh_secret, hash_secret

router = APIRouter(prefix="/groups", tags=["groups"])


def _membership_response(membership: GroupMembership) -> MembershipResponse:
    return MembershipResponse(group_id=membership.group_id, user_id=membership.user_id, role=membership.role)


def _join_request_response(join_request: GroupJoinRequest) -> JoinRequestResponse:
    return JoinRequestResponse(
        id=join_request.id,
        group_id=join_request.group_id,
        user_id=join_request.user_id,
        status=join_request.status,
        created_at=join_request.created_at,
        reviewed_by=join_request.reviewed_by,
        reviewed_at=join_request.reviewed_at,
    )


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupResponse:
    group = Group(name=payload.name, description=payload.description, created_by=current_user.id)
    db.add(group)
    db.flush()
    membership = GroupMembership(group_id=group.id, user_id=current_user.id, role="owner")
    db.add(membership)
    db.commit()
    db.refresh(group)
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        created_by=group.created_by,
        created_at=group.created_at,
        role="owner",
    )


@router.get("", response_model=list[GroupResponse])
def list_groups(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[GroupResponse]:
    rows = db.execute(
        select(Group, GroupMembership.role)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(GroupMembership.user_id == current_user.id)
    ).all()
    return [
        GroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            created_by=group.created_by,
            created_at=group.created_at,
            role=role,
        )
        for group, role in rows
    ]


@router.get("/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupResponse:
    membership = get_membership_or_404(db, current_user.id, group_id)
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        created_by=group.created_by,
        created_at=group.created_at,
        role=membership.role,
    )


@router.post("/{group_id}/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def create_invite(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InviteResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    if db.get(Group, group_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    invite_code = generate_refresh_secret()
    expires_at = utc_now() + timedelta(days=7)
    invite = GroupInvite(
        group_id=group_id,
        invite_code_hash=hash_secret(invite_code),
        created_by=current_user.id,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    return InviteResponse(group_id=group_id, invite_code=invite_code, expires_at=expires_at)


@router.post("/join-by-invite", response_model=MembershipResponse)
def join_by_invite(
    payload: JoinByInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MembershipResponse:
    invite = db.scalar(select(GroupInvite).where(GroupInvite.invite_code_hash == hash_secret(payload.invite_code)))
    now = utc_now()
    if invite is None or invite.revoked_at is not None or as_utc(invite.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    existing = db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == invite.group_id,
            GroupMembership.user_id == current_user.id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a group member")

    membership = GroupMembership(group_id=invite.group_id, user_id=current_user.id, role="member")
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return _membership_response(membership)


@router.post("/{group_id}/join-requests", response_model=JoinRequestResponse, status_code=status.HTTP_201_CREATED)
def create_join_request(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JoinRequestResponse:
    if db.get(Group, group_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    existing_member = db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
        )
    )
    if existing_member is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a group member")

    pending = db.scalar(
        select(GroupJoinRequest).where(
            GroupJoinRequest.group_id == group_id,
            GroupJoinRequest.user_id == current_user.id,
            GroupJoinRequest.status == "pending",
        )
    )
    if pending is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Join request already pending")

    join_request = GroupJoinRequest(group_id=group_id, user_id=current_user.id, status="pending")
    db.add(join_request)
    db.commit()
    db.refresh(join_request)
    return _join_request_response(join_request)


@router.get("/{group_id}/join-requests", response_model=list[JoinRequestResponse])
def list_join_requests(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[JoinRequestResponse]:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    requests = db.scalars(
        select(GroupJoinRequest).where(
            GroupJoinRequest.group_id == group_id,
            GroupJoinRequest.status == "pending",
        )
    ).all()
    return [_join_request_response(join_request) for join_request in requests]


@router.post("/{group_id}/join-requests/{request_id}/approve", response_model=JoinRequestResponse)
def approve_join_request(
    group_id: str,
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JoinRequestResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    join_request = db.scalar(
        select(GroupJoinRequest).where(
            GroupJoinRequest.id == request_id,
            GroupJoinRequest.group_id == group_id,
        )
    )
    if join_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Join request not found")
    if join_request.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Join request already reviewed")

    existing_member = db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == join_request.user_id,
        )
    )
    if existing_member is None:
        db.add(GroupMembership(group_id=group_id, user_id=join_request.user_id, role="member"))

    join_request.status = "approved"
    join_request.reviewed_by = current_user.id
    join_request.reviewed_at = utc_now()
    db.commit()
    db.refresh(join_request)
    return _join_request_response(join_request)


@router.post("/{group_id}/join-requests/{request_id}/reject", response_model=JoinRequestResponse)
def reject_join_request(
    group_id: str,
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JoinRequestResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    join_request = db.scalar(
        select(GroupJoinRequest).where(
            GroupJoinRequest.id == request_id,
            GroupJoinRequest.group_id == group_id,
        )
    )
    if join_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Join request not found")
    if join_request.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Join request already reviewed")

    join_request.status = "rejected"
    join_request.reviewed_by = current_user.id
    join_request.reviewed_at = utc_now()
    db.commit()
    db.refresh(join_request)
    return _join_request_response(join_request)


@router.patch("/{group_id}/members/{user_id}/role", response_model=MembershipResponse)
def update_member_role(
    group_id: str,
    user_id: str,
    payload: RoleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MembershipResponse:
    require_group_role(db, current_user.id, group_id, {"owner"})
    target = db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
        )
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if target.role == "owner" and payload.role != "owner":
        owner_count = db.scalar(
            select(func.count()).select_from(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.role == "owner",
            )
        )
        if owner_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote the last owner")

    target.role = payload.role
    db.commit()
    db.refresh(target)
    return _membership_response(target)
