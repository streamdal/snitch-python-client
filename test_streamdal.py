import asyncio
import threading
import pytest
import streamdal_protos.protos as protos
import uuid
import unittest.mock as mock
import streamdal
from streamdal import StreamdalClient, StreamdalConfig


class TestStreamdalClient:
    client: StreamdalClient

    @pytest.fixture(autouse=True)
    def before_each(self):
        client = object.__new__(StreamdalClient)
        client.cfg = StreamdalConfig(service_name="testing")
        client.grpc_loop = asyncio.get_event_loop()
        client.log = mock.Mock()
        client.metrics = mock.Mock()
        client.grpc_stub = mock.AsyncMock()
        client.register_stub = mock.AsyncMock()
        client.grpc_loop = asyncio.get_event_loop()
        client.register_loop = asyncio.get_event_loop()
        client.grpc_timeout = 5
        client.auth_token = "test"
        client.exit = threading.Event()
        client.session_id = uuid.uuid4().__str__()
        client.pipelines = {}
        client.paused_pipelines = {}
        client.audiences = {}
        client.tails = {}
        client.schemas = {}

        self.client = client

    def test_process_validation(self):
        with pytest.raises(ValueError, match="req is required"):
            self.client.process(None)

    def test_process_max_size(self):
        fake_metrics = mock.Mock()

        self.client.cfg = StreamdalConfig(service_name="testing")
        self.client.metrics = fake_metrics
        payload = bytearray(streamdal.MAX_PAYLOAD_SIZE + 1)
        payload_bytes = bytes(payload)

        req = streamdal.ProcessRequest(
            data=payload_bytes,
            operation_type=1,
            component_name="kafka",
            operation_name="test-topic",
        )
        res = self.client.process(req)

        assert res is not None
        assert res.data == payload_bytes
        fake_metrics.incr.assert_called_once()

    def test_notify_condition(self):
        fake_stub = mock.AsyncMock()
        fake_metrics = mock.Mock()

        self.client.metrics = fake_metrics
        self.client.grpc_stub = fake_stub

        pipeline = protos.Pipeline(id=uuid.uuid4().__str__())
        step = protos.PipelineStep(name="test")
        aud = protos.Audience()

        self.client._notify_condition(pipeline, step, aud)
        fake_stub.notify.assert_called_once()
        fake_metrics.incr.assert_called_once()

    # def test_heartbeat(self):
    #     fake_stub = mock.AsyncMock()
    #
    #     self.client.grpc_stub = fake_stub
    #     self.client.exit.set()
    #
    #     hb = threading.Thread(target=self.client._heartbeat())
    #     hb.start()
    #     hb.join()
    #     fake_stub.heartbeat.assert_called_once()

    def test_op_to_string(self):
        assert (
            StreamdalClient.op_to_string(protos.OperationType.OPERATION_TYPE_PRODUCER)
            == "producer"
        )
        assert (
            StreamdalClient.op_to_string(protos.OperationType.OPERATION_TYPE_CONSUMER)
            == "consumer"
        )
        assert (
            StreamdalClient.op_to_string(protos.OperationType.OPERATION_TYPE_UNSET)
            == "consumer"
        )

    def test_process_success(self):
        wasm_resp = protos.WasmResponse(
            output_payload=b'{"object": {"type": "streamdal"}}',
            exit_code=protos.WasmExitCode.WASM_EXIT_CODE_SUCCESS,
            exit_msg="",
        )
        self.client._call_wasm = mock.MagicMock()
        self.client._call_wasm.return_value = wasm_resp

        cmd = protos.Command(
            audience=protos.Audience(
                component_name="test",
                service_name="testing",
                operation_type=protos.OperationType.OPERATION_TYPE_PRODUCER,
            ),
            attach_pipeline=protos.AttachPipelineCommand(
                pipeline=protos.Pipeline(
                    id=uuid.uuid4().__str__(),
                    steps=[
                        protos.PipelineStep(
                            name="test",
                            on_success=[
                                protos.PipelineStepCondition.PIPELINE_STEP_CONDITION_UNSET
                            ],
                            on_failure=[
                                protos.PipelineStepCondition.PIPELINE_STEP_CONDITION_ABORT
                            ],
                            detective=protos.steps.DetectiveStep(
                                path="object.type",
                                args=["streamdal"],
                                type=protos.steps.DetectiveType.DETECTIVE_TYPE_STRING_CONTAINS_ANY,
                            ),
                        )
                    ],
                )
            ),
        )

        self.client._attach_pipeline(cmd)

        resp = self.client.process(
            streamdal.ProcessRequest(
                data=b'{"object": {"type": "streamdal"}}',
                operation_type=streamdal.MODE_PRODUCER,
                component_name="kafka",
                operation_name="test-topic",
            )
        )

        assert resp is not None
        assert resp.error is False
        assert resp.message == ""
        assert resp.data == b'{"object": {"type": "streamdal"}}'

    def test_process_failure(self):
        fake_stub = mock.AsyncMock()

        client = self.client
        client.grpc_stub = fake_stub

        wasm_resp = protos.WasmResponse(
            output_payload=b"{}",
            exit_code=protos.WasmExitCode.WASM_EXIT_CODE_FAILURE,
            exit_msg="field not found",
        )
        client._call_wasm = mock.MagicMock()
        client._call_wasm.return_value = wasm_resp

        cmd = protos.Command(
            audience=protos.Audience(
                component_name="kafka",
                operation_name="test-topic",
                service_name="testing",
                operation_type=protos.OperationType.OPERATION_TYPE_PRODUCER,
            ),
            attach_pipeline=protos.AttachPipelineCommand(
                pipeline=protos.Pipeline(
                    id=uuid.uuid4().__str__(),
                    steps=[
                        protos.PipelineStep(
                            name="test",
                            on_success=[],
                            on_failure=[
                                protos.PipelineStepCondition.PIPELINE_STEP_CONDITION_ABORT,
                                protos.PipelineStepCondition.PIPELINE_STEP_CONDITION_NOTIFY,
                            ],
                            detective=protos.steps.DetectiveStep(
                                path="object.type",
                                args=["batch"],
                                type=protos.steps.DetectiveType.DETECTIVE_TYPE_STRING_CONTAINS_ANY,
                            ),
                        )
                    ],
                )
            ),
        )

        client._attach_pipeline(cmd)

        resp = client.process(
            streamdal.ProcessRequest(
                data=b'{"object": {"type": "streamdal"}}',
                operation_type=streamdal.MODE_PRODUCER,
                component_name="kafka",
                operation_name="test-topic",
            )
        )

        assert resp is not None
        assert resp.error is True
        assert resp.message == "field not found"
        assert resp.data == b"{}"
        fake_stub.notify.assert_called_once()

    def test_process_failure_dry_run(self):
        client = self.client
        client.cfg = StreamdalConfig(dry_run=True)

        wasm_resp = protos.WasmResponse(
            output_payload=b'{"object": {"type": "should be replaced by original data on dry run"}}',
            exit_code=protos.WasmExitCode.WASM_EXIT_CODE_FAILURE,
            exit_msg="field not found",
        )
        client._call_wasm = mock.MagicMock()
        client._call_wasm.return_value = wasm_resp

        cmd = protos.Command(
            audience=protos.Audience(
                component_name="test-topic",
                service_name="testing",
                operation_type=protos.OperationType.OPERATION_TYPE_PRODUCER,
            ),
            attach_pipeline=protos.AttachPipelineCommand(
                pipeline=protos.Pipeline(
                    id=uuid.uuid4().__str__(),
                    steps=[
                        protos.PipelineStep(
                            name="test",
                            on_success=[],
                            on_failure=[
                                protos.PipelineStepCondition.PIPELINE_STEP_CONDITION_ABORT
                            ],
                            detective=protos.steps.DetectiveStep(
                                path="object.type",
                                args=["batch"],
                                type=protos.steps.DetectiveType.DETECTIVE_TYPE_STRING_CONTAINS_ANY,
                            ),
                        )
                    ],
                )
            ),
        )

        client._attach_pipeline(cmd)

        resp = client.process(
            streamdal.ProcessRequest(
                data=b'{"object": {"type": "streamdal"}}',
                operation_type=streamdal.MODE_PRODUCER,
                component_name="kafka",
                operation_name="test-topic",
            )
        )

        assert resp is not None
        assert resp.error is False
        assert resp.message == ""
        assert resp.data == b'{"object": {"type": "streamdal"}}'

    def test_aud_to_str(self):
        aud = protos.Audience(
            component_name="kafka",
            service_name="testing",
            operation_name="test-topic",
            operation_type=protos.OperationType.OPERATION_TYPE_PRODUCER,
        )

        assert self.client._aud_to_str(aud) == "testing.kafka.2.test-topic"

    def test_str_to_aud(self):
        aud = protos.Audience(
            component_name="kafka",
            service_name="testing",
            operation_name="test-topic",
            operation_type=protos.OperationType.OPERATION_TYPE_PRODUCER,
        )

        parsed = self.client._str_to_aud("testing.kafka.2.test-topic")
        assert parsed.component_name == aud.component_name
        assert parsed.service_name == aud.service_name
        assert parsed.operation_name == aud.operation_name
        assert parsed.operation_type == aud.operation_type