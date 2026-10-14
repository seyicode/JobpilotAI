import uuid

from samples import SAMPLE_TEXT, make_pdf

from jobpilot.core.config import Settings, get_settings

SAMPLE_BYTES = SAMPLE_TEXT.encode()


def upload(client, filename="resume.txt", data=SAMPLE_BYTES):
    return client.post("/resumes", files={"file": (filename, data, "application/octet-stream")})


def test_upload_parses_and_stores_resume(db_client):
    response = upload(db_client)
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "resume.txt"
    assert body["file_type"] == "txt"
    assert body["size_bytes"] == len(SAMPLE_BYTES)
    assert [s["key"] for s in body["sections"]][:3] == ["header", "summary", "experience"]

    fetched = db_client.get(f"/resumes/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_list_returns_newest_first_without_contents(db_client):
    first = upload(db_client, "first.txt").json()
    second = upload(db_client, "second.pdf", make_pdf(["Skills", "Python"])).json()
    listed = db_client.get("/resumes").json()
    assert [r["id"] for r in listed] == [second["id"], first["id"]]
    assert "text" not in listed[0] and "sections" not in listed[0]


def test_delete_removes_resume(db_client):
    resume_id = upload(db_client).json()["id"]
    assert db_client.delete(f"/resumes/{resume_id}").status_code == 204
    assert db_client.get(f"/resumes/{resume_id}").status_code == 404
    assert db_client.delete(f"/resumes/{resume_id}").status_code == 404


def test_unknown_and_malformed_ids(db_client):
    assert db_client.get(f"/resumes/{uuid.uuid4()}").status_code == 404
    assert db_client.get("/resumes/not-a-uuid").status_code == 422


def test_rejects_invalid_file_without_storing(db_client):
    response = upload(db_client, "resume.pdf", b"not a pdf")
    assert response.status_code == 422
    assert response.json() == {"detail": "This file is not a valid PDF."}
    assert db_client.get("/resumes").json() == []


def test_rejects_empty_file(db_client):
    response = upload(db_client, data=b"")
    assert response.status_code == 422
    assert response.json() == {"detail": "The uploaded file is empty."}


def test_rejects_oversized_file(db_client):
    limit = 1024 * 1024
    db_client.app.dependency_overrides[get_settings] = lambda: Settings(max_resume_bytes=limit)
    response = upload(db_client, data=b"a" * (limit + 1))
    assert response.status_code == 413
    assert response.json() == {"detail": "Resumes must be 1 MB or smaller."}


def test_filename_path_is_stripped(db_client):
    response = upload(db_client, "../../etc/C:\\Users\\me\\cv.txt")
    assert response.json()["filename"] == "cv.txt"
