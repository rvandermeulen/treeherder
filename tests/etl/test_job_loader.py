import copy
import uuid

import pytest
import responses
import slugid
from django.core.exceptions import ObjectDoesNotExist

from treeherder.etl.job_loader import JobLoader
from treeherder.etl.taskcluster_pulse.handler import handle_message
from treeherder.model.models import Job, JobLog, TaskclusterMetadata


@pytest.fixture
def first_job(sample_data, test_repository, push_stored):
    revision = push_stored[0]["revisions"][0]["revision"]
    job = copy.deepcopy(sample_data.pulse_jobs[0])
    job["origin"]["project"] = test_repository.name
    job["origin"]["revision"] = revision
    return job


@pytest.fixture
def pulse_jobs(sample_data, test_repository, push_stored):
    revision = push_stored[0]["revisions"][0]["revision"]
    jobs = copy.deepcopy(sample_data.pulse_jobs)
    for job in jobs:
        job["origin"]["project"] = test_repository.name
        job["origin"]["revision"] = revision
    return jobs


@pytest.fixture
def transformed_pulse_jobs(sample_data, test_repository):
    jobs = copy.deepcopy(sample_data.transformed_pulse_jobs)
    return jobs


def mock_artifact(task_id, run_id, artifact_name):
    # Mock artifact with empty body
    base_url = (
        "https://taskcluster.net/api/queue/v1/task/{taskId}/runs/{runId}/artifacts/{artifactName}"
    )
    responses.add(
        responses.GET,
        base_url.format(taskId=task_id, runId=run_id, artifactName=artifact_name),
        body="",
        content_type="text/plain",
        status=200,
    )


@pytest.fixture
async def new_pulse_jobs(sample_data, test_repository, push_stored):
    revision = push_stored[0]["revisions"][0]["revision"]
    pulse_messages = copy.deepcopy(sample_data.taskcluster_pulse_messages)
    tasks = copy.deepcopy(sample_data.taskcluster_tasks)
    jobs = []
    # Over here we transform the Pulse messages into the intermediary taskcluster-treeherder
    # generated messages
    for message in list(pulse_messages.values()):
        task_id = message["payload"]["status"]["taskId"]
        task = tasks[task_id]

        # If we pass task to handle_message we won't hit the network
        task_runs = await handle_message(message, task)
        # handle_message returns [] when it is a task that is not meant for Treeherder
        for run in reversed(task_runs):
            mock_artifact(task_id, run["retryId"], "public/logs/live_backing.log")
            run["origin"]["project"] = test_repository.name
            run["origin"]["revision"] = revision
            jobs.append(run)
    return jobs


@pytest.fixture
def new_transformed_jobs(sample_data, test_repository, push_stored):
    revision = push_stored[0]["revisions"][0]["revision"]
    jobs = copy.deepcopy(sample_data.taskcluster_transformed_jobs)
    for job in jobs.values():
        job["revision"] = revision
    return jobs


def test_job_transformation(pulse_jobs, transformed_pulse_jobs):
    import json

    jl = JobLoader()
    for idx, pulse_job in enumerate(pulse_jobs):
        assert jl._is_valid_job(pulse_job)
        assert transformed_pulse_jobs[idx] == json.loads(json.dumps(jl.transform(pulse_job)))


@responses.activate
def test_new_job_transformation(new_pulse_jobs, new_transformed_jobs, failure_classifications):
    jl = JobLoader()
    for message in new_pulse_jobs:
        # "task_id" which is not really the task_id
        job_guid = message["taskId"]
        (decoded_task_id, _) = job_guid.split("/")
        # As of slugid v2, slugid.encode() returns a string not bytestring under Python 3.
        task_id = slugid.encode(uuid.UUID(decoded_task_id))
        transformed_job = jl.process_job(message, "https://firefox-ci-tc.services.mozilla.com")
        # Not all messages from Taskcluster will be processed
        if transformed_job:
            assert new_transformed_jobs[task_id] == transformed_job


def test_ingest_pulse_jobs(
    pulse_jobs, test_repository, push_stored, failure_classifications, mock_log_parser
):
    """
    Ingest a job through the JSON Schema validated JobLoader used by Pulse
    """

    jl = JobLoader()
    revision = push_stored[0]["revision"]
    for job in pulse_jobs:
        job["origin"]["revision"] = revision
        jl.process_job(job, "https://firefox-ci-tc.services.mozilla.com")

    jobs = Job.objects.all()
    assert len(jobs) == 30

    assert [job.taskcluster_metadata for job in jobs]
    assert set(TaskclusterMetadata.objects.values_list("task_id", flat=True)) == set(
        [
            "AI3Nrr3gSDSpZ9E9aBA3rg",
            "BAG7ifS1QbGCDwiOP7NklQ",
            "CaK6NlfBSf6F-NAVrrKJDQ",
            "CilZCnmiTKmagJe_h6Hq5A",
            "FNT3BLiQRHO14NNgonjQQg",
            "FcbIUoVbS4utxFES84wrPw",
            "FclD6gA-TTGgvq_r9-LSDg",
            "GPLk78m6Sz6TTLJFVca4Xw",
            "GcvHP6HLSeO_rKYDN2y_Tg",
            "I-Hg7bM4TUOq4JqnX0pt0g",
            "I2Y-TBNcQPSJzsKlB95rfQ",
            "M1ECjPJBTlmwJxZq5pWyvg",
            "MKq8mMM-RIOxztXO5ng-_A",
            "MrrbifzBQJefUbS2ym4Qag",
            "ORYYNMhET0yxGMvel4Jujg",
            "TqWDDGoWSbCH93RTTxPAWg",
            "V8rtIDroRV-G9bzjJglS0A",
            "VVa2amzMS-2cSDbig9RHsw",
            "YIOK401yR2GvygIFcfPVBg",
            "b_QCzMjVQmKPyO5Il0Jedw",
            "bljbLRFdT4KGCWJ2_C6RsQ",
            "c2dxYucCSMWPlTkb70r89g",
            "cPe8y071Spat09dlAzCGug",
            "cZ7gc9JYQa2UPEC_EIxIug",
            "dB8R5AXORZeCpDfQlYUlow",
            "e1YPllz6TMawISpugkRx1g",
            "eJ9PG41tSaWzNU1uY7-uSQ",
            "edzgzCphTAS-QN_TAnf7eA",
            "ekQaeC_yR0K8jPKx28E7EA",
            "ftXsRyOwRgeiiYHyITXUOA",
        ]
    )

    job_logs = JobLog.objects.filter(job_id=1)
    assert job_logs.count() == 1
    logs_expected = [
        {
            "name": "live_backing_log",
            "url": "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/AI3Nrr3gSDSpZ9E9aBA3rg/runs/0/artifacts/public/logs/live_backing.log",
            "parse_status": 0,
        },
    ]
    assert [
        {"name": item.name, "url": item.url, "parse_status": item.status}
        for item in job_logs.all().order_by("name")
    ] == logs_expected


def test_ingest_pulse_job_with_long_job_type_name(
    pulse_jobs, test_repository, push_stored, failure_classifications, mock_log_parser
):
    """
    Ingest a job through the JSON Schema validated JobLoader used by Pulse
    """
    job = pulse_jobs[0]
    jl = JobLoader()
    revision = push_stored[0]["revision"]
    job["display"]["jobName"] = (
        "this is a very long string that exceeds the 100 character size that was the previous limit by just a little bit"
    )
    job["origin"]["revision"] = revision
    jl.process_job(job, "https://firefox-ci-tc.services.mozilla.com")

    jobs = Job.objects.all()
    assert len(jobs) == 1


def test_ingest_pending_pulse_job(
    pulse_jobs, push_stored, failure_classifications, mock_log_parser
):
    """
    Test that ingesting a pending job (1) works and (2) ingests the
    taskcluster metadata
    """
    jl = JobLoader()

    pulse_job = pulse_jobs[0]
    revision = push_stored[0]["revision"]
    pulse_job["origin"]["revision"] = revision
    pulse_job["state"] = "pending"
    jl.process_job(pulse_job, "https://firefox-ci-tc.services.mozilla.com")

    jobs = Job.objects.all()
    assert len(jobs) == 1

    job = jobs[0]
    assert job.taskcluster_metadata
    assert job.taskcluster_metadata.task_id == "AI3Nrr3gSDSpZ9E9aBA3rg"

    # should not have processed any log or details for pending jobs
    assert JobLog.objects.count() == 1


def test_ingest_pulse_jobs_bad_project(
    pulse_jobs, test_repository, push_stored, failure_classifications, mock_log_parser
):
    """
    Test ingesting a pulse job with bad repo will skip, ingest others
    """

    jl = JobLoader()
    revision = push_stored[0]["revision"]
    job = pulse_jobs[0]
    job["origin"]["revision"] = revision
    job["origin"]["project"] = "ferd"

    for pulse_job in pulse_jobs:
        jl.process_job(pulse_job, "https://firefox-ci-tc.services.mozilla.com")

    # length of pulse jobs is 5, so one will be skipped due to bad project
    assert Job.objects.count() == 29


@responses.activate
def test_ingest_pulse_jobs_with_missing_push(pulse_jobs):
    """
    Ingest jobs with missing pushes, so they should throw an exception
    """

    jl = JobLoader()
    job = pulse_jobs[0]
    job["origin"]["revision"] = "1234567890123456789012345678901234567890"
    responses.add(
        responses.GET,
        "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/AI3Nrr3gSDSpZ9E9aBA3rg",
        json={},
        content_type="application/json",
        status=200,
    )

    with pytest.raises(ObjectDoesNotExist):
        for pulse_job in pulse_jobs:
            jl.process_job(pulse_job, "https://firefox-ci-tc.services.mozilla.com")

    # if one job isn't ready, except on the whole batch.  They'll retry as a
    # task after the timeout.
    assert Job.objects.count() == 0


def test_transition_pending_running_complete(first_job, failure_classifications, mock_log_parser):
    jl = JobLoader()

    change_state_result(first_job, jl, "pending", "unknown", "pending", "unknown")
    change_state_result(first_job, jl, "running", "unknown", "running", "unknown")
    change_state_result(first_job, jl, "completed", "fail", "completed", "testfailed")


def test_transition_complete_pending_stays_complete(
    first_job, failure_classifications, mock_log_parser
):
    jl = JobLoader()

    change_state_result(first_job, jl, "completed", "fail", "completed", "testfailed")
    change_state_result(first_job, jl, "pending", "unknown", "completed", "testfailed")


def test_transition_complete_running_stays_complete(
    first_job, failure_classifications, mock_log_parser
):
    jl = JobLoader()

    change_state_result(first_job, jl, "completed", "fail", "completed", "testfailed")
    change_state_result(first_job, jl, "running", "unknown", "completed", "testfailed")


def test_transition_running_pending_stays_running(
    first_job, failure_classifications, mock_log_parser
):
    jl = JobLoader()

    change_state_result(first_job, jl, "running", "unknown", "running", "unknown")
    change_state_result(first_job, jl, "pending", "unknown", "running", "unknown")


def test_transition_running_superseded(first_job, failure_classifications, mock_log_parser):
    jl = JobLoader()

    change_state_result(first_job, jl, "running", "unknown", "running", "unknown")
    change_state_result(first_job, jl, "completed", "superseded", "completed", "superseded")


def test_transition_pending_retry_fail_stays_retry(
    first_job, failure_classifications, mock_log_parser
):
    jl = JobLoader()

    change_state_result(first_job, jl, "pending", "unknown", "pending", "unknown")
    first_job["isRetried"] = True
    change_state_result(first_job, jl, "completed", "fail", "completed", "retry")
    first_job["isRetried"] = False
    change_state_result(first_job, jl, "completed", "fail", "completed", "retry")


def test_skip_unscheduled(first_job, failure_classifications, mock_log_parser):
    jl = JobLoader()
    first_job["state"] = "unscheduled"
    jl.process_job(first_job, "https://firefox-ci-tc.services.mozilla.com")

    assert not Job.objects.count()


def change_state_result(test_job, job_loader, new_state, new_result, exp_state, exp_result):
    # make a copy so we can modify it and not affect other tests
    job = copy.deepcopy(test_job)
    job["state"] = new_state
    job["result"] = new_result
    if new_state == "pending":
        # pending jobs wouldn't have logs and our store_job_data doesn't
        # support it.
        del job["logs"]
        errorsummary_indices = [
            i
            for i, item in enumerate(job["jobInfo"].get("links", []))
            if item.get("linkText", "").endswith("_errorsummary.log")
        ]
        for index in errorsummary_indices:
            del job["jobInfo"]["links"][index]

    job_loader.process_job(job, "https://firefox-ci-tc.services.mozilla.com")

    assert Job.objects.count() == 1
    job = Job.objects.get(id=1)
    assert job.state == exp_state
    assert job.result == exp_result
