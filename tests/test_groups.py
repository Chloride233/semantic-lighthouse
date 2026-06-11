from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.models import GroupMembership
from tests.conftest import register_and_login


def test_owner_can_create_group(client):
    _, _, owner_headers = register_and_login(client, "owner@example.com")

    response = client.post(
        "/groups",
        json={"name": "Manufacturing Team", "description": "Factory AI transformation"},
        headers=owner_headers,
    )

    assert response.status_code == 201
    assert response.json()["role"] == "owner"


def test_invite_join_creates_member(client):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = client.post("/groups", json={"name": "Team"}, headers=owner_headers).json()["id"]
    invite = client.post(f"/groups/{group_id}/invites", headers=owner_headers).json()["invite_code"]

    _, _, member_headers = register_and_login(client, "member@example.com")
    join_response = client.post("/groups/join-by-invite", json={"invite_code": invite}, headers=member_headers)

    assert join_response.status_code == 200
    assert join_response.json()["role"] == "member"
    group_response = client.get(f"/groups/{group_id}", headers=member_headers)
    assert group_response.status_code == 200


def test_join_request_requires_owner_or_admin_to_approve(client):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = client.post("/groups", json={"name": "Team"}, headers=owner_headers).json()["id"]
    invite = client.post(f"/groups/{group_id}/invites", headers=owner_headers).json()["invite_code"]

    _, _, member_headers = register_and_login(client, "member@example.com")
    client.post("/groups/join-by-invite", json={"invite_code": invite}, headers=member_headers)

    _, _, applicant_headers = register_and_login(client, "applicant@example.com")
    request_response = client.post(f"/groups/{group_id}/join-requests", headers=applicant_headers)
    request_id = request_response.json()["id"]

    member_list_response = client.get(f"/groups/{group_id}/join-requests", headers=member_headers)
    assert member_list_response.status_code == 403

    member_approve_response = client.post(
        f"/groups/{group_id}/join-requests/{request_id}/approve",
        headers=member_headers,
    )
    assert member_approve_response.status_code == 403

    owner_approve_response = client.post(
        f"/groups/{group_id}/join-requests/{request_id}/approve",
        headers=owner_headers,
    )
    assert owner_approve_response.status_code == 200
    assert owner_approve_response.json()["status"] == "approved"


def test_admin_can_approve_but_cannot_downgrade_owner(client):
    owner_user, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = client.post("/groups", json={"name": "Team"}, headers=owner_headers).json()["id"]
    invite = client.post(f"/groups/{group_id}/invites", headers=owner_headers).json()["invite_code"]

    admin_user, _, admin_headers = register_and_login(client, "admin@example.com")
    client.post("/groups/join-by-invite", json={"invite_code": invite}, headers=admin_headers)
    promote_response = client.patch(
        f"/groups/{group_id}/members/{admin_user['id']}/role",
        json={"role": "admin"},
        headers=owner_headers,
    )
    assert promote_response.status_code == 200

    _, _, applicant_headers = register_and_login(client, "applicant@example.com")
    request_response = client.post(f"/groups/{group_id}/join-requests", headers=applicant_headers)
    approve_response = client.post(
        f"/groups/{group_id}/join-requests/{request_response.json()['id']}/approve",
        headers=admin_headers,
    )
    assert approve_response.status_code == 200

    downgrade_owner_response = client.patch(
        f"/groups/{group_id}/members/{owner_user['id']}/role",
        json={"role": "member"},
        headers=admin_headers,
    )
    assert downgrade_owner_response.status_code == 403


def test_non_member_cannot_access_group(client):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = client.post("/groups", json={"name": "Team"}, headers=owner_headers).json()["id"]
    _, _, outsider_headers = register_and_login(client, "outsider@example.com")

    response = client.get(f"/groups/{group_id}", headers=outsider_headers)

    assert response.status_code == 403


def test_group_queries_are_filtered_by_group_id(client, db_session: Session):
    owner_user, _, owner_headers = register_and_login(client, "owner@example.com")
    group_a = client.post("/groups", json={"name": "A"}, headers=owner_headers).json()["id"]
    group_b = client.post("/groups", json={"name": "B"}, headers=owner_headers).json()["id"]

    membership = db_session.scalar(
        select(GroupMembership).where(
            GroupMembership.user_id == owner_user["id"],
            GroupMembership.group_id == group_a,
        )
    )
    assert membership is not None
    assert membership.group_id != group_b

