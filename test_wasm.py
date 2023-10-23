import streamdal.common as common
import streamdal_protos.protos as protos
import uuid
from streamdal import StreamdalClient
from wasmtime import Store, Memory, MemoryType, Limits


class TestStreamdalWasm:
    def test_call_wasm_failure(self, mocker):
        mocker.patch(
            "streamdal.StreamdalClient._exec_wasm",
            side_effect=Exception("something happened"),
        )
        client = object.__new__(StreamdalClient)

        step = protos.PipelineStep()

        res = client._call_wasm(step=step, data=b"")

        assert res is not None
        assert res.exit_code == 3

    def test_detective_wasm(self):
        """Test we can execute the detective wasm file"""

        client = object.__new__(StreamdalClient)
        client.functions = {}

        with open("./assets/test/detective.wasm", "rb") as file:
            wasm_bytes = file.read()

        step = protos.PipelineStep(
            name="detective",
            on_success=[],
            on_failure=[],
            wasm_bytes=wasm_bytes,
            wasm_id=uuid.uuid4().__str__(),
            wasm_function="f",
            detective=protos.steps.DetectiveStep(
                path="object.field",
                args=["streamdal"],
                negate=False,
                type=protos.steps.DetectiveType.DETECTIVE_TYPE_STRING_CONTAINS_ANY,
            ),
        )

        res = client._call_wasm(
            step=step, data=b'{"object":  {"field": "streamdal@gmail.com"}}'
        )

        assert res is not None
        assert res.exit_code == 1
        assert res.output_payload == b'{"object":  {"field": "streamdal@gmail.com"}}'

        res2 = client._call_wasm(
            step=step, data=b'{"object":  {"field": "mark@gmail.com"}}'
        )

        assert res2 is not None
        assert res2.exit_code == 2

    def test_http_request_wasm(self):
        """Test we can execute a wasm file"""

        client = object.__new__(StreamdalClient)
        client.functions = {}

        with open("./assets/test/httprequest.wasm", "rb") as file:
            wasm_bytes = file.read()

        step = protos.PipelineStep(
            name="httprequest test",
            on_success=[],
            on_failure=[],
            wasm_bytes=wasm_bytes,
            wasm_id=uuid.uuid4().__str__(),
            wasm_function="f",
            http_request=protos.steps.HttpRequestStep(
                request=protos.steps.HttpRequest(
                    url="https://www.streamdal.com/404_me",
                    method=protos.steps.HttpRequestMethod.HTTP_REQUEST_METHOD_GET,
                ),
            ),
        )

        res = client._call_wasm(step=step, data=b"")

        assert res is not None
        assert res.exit_code == 2
        assert res.exit_msg == "Request returned non-200 response code: 404"

    def test_infer_schema(self):
        """Test we can infer schema from json using the wasm module"""

        client = object.__new__(StreamdalClient)
        client.functions = {}

        with open("./assets/test/inferschema.wasm", "rb") as file:
            wasm_bytes = file.read()

        step = protos.PipelineStep(
            name="inferschema test",
            on_success=[],
            on_failure=[],
            wasm_bytes=wasm_bytes,
            wasm_id=uuid.uuid4().__str__(),
            wasm_function="f",
            infer_schema=protos.steps.InferSchemaStep(current_schema=b""),
        )

        res = client._call_wasm(step=step, data=b'{"object": {"payload": "test"}}')

        assert res is not None
        assert res.exit_code == 1
        assert res.exit_msg == "inferred fresh schema"
        assert res.output_payload == b'{"object": {"payload": "test"}}'
        assert (
            res.output_step
            == b'{"$schema":"http://json-schema.org/draft-07/schema#","properties":{"object":{"properties":{'
            b'"payload":{"type":"string"}},"required":["payload"],"type":"object"}},"required":["object"],'
            b'"type":"object"}'
        )

    def test_transform_wasm(self):
        """Test we can execute the transform wasm module"""

        client = object.__new__(StreamdalClient)
        client.functions = {}

        with open("./assets/test/transform.wasm", "rb") as file:
            wasm_bytes = file.read()

        step = protos.PipelineStep(
            name="transform test",
            on_success=[],
            on_failure=[],
            wasm_bytes=wasm_bytes,
            wasm_id=uuid.uuid4().__str__(),
            wasm_function="f",
            transform=protos.steps.TransformStep(
                path="object.payload",
                value='"new val"',
                type=protos.steps.TransformType.TRANSFORM_TYPE_REPLACE_VALUE,
            ),
        )

        res = client._call_wasm(step=step, data=b'{"object": {"payload": "old val"}}')

        assert res is not None
        assert res.exit_code == 1
        assert res.exit_msg == "Successfully transformed payload"
        assert res.output_payload == b'{"object": {"payload": "new val"}}'
