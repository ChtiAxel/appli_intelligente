import asyncio
import base64
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from NaturSQL.ollama_client.llm import LLMClient
from NaturSQL.ollama_client.ollama_wrapper_iut import (
    OllamaConnectionError,
    OllamaResponseError,
    OllamaWrapper,
)


class OllamaTests(unittest.TestCase):
    def test_url_parsing_and_model_status(self):
        client = OllamaWrapper("http://localhost:1234/")
        self.assertEqual(client._parse_host_port(), ("localhost", 1234))
        client.get_version = Mock(return_value="0.1")
        self.assertTrue(client.is_server_running())
        client.get_version.side_effect = OllamaConnectionError("offline")
        self.assertFalse(client.is_server_running())
        client.get_version.side_effect = OllamaResponseError("bad")
        self.assertTrue(client.is_server_running())

    def test_list_models_filters_invalid_entries(self):
        client = OllamaWrapper()
        client._http_request_json = Mock(return_value={
            "models": [
                {"name": "llama3", "size": 10, "details": {"family": "llama"}},
                {"name": 123},
                "invalid",
            ]
        })
        models = client.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].name, "llama3")
        self.assertEqual(models[0].details.family, "llama")

    def test_generation_embedding_and_image_payloads(self):
        client = OllamaWrapper()
        client._http_request_json = Mock(return_value={"response": " answer ", "done": True})
        result = client.generate_text(model="llama", prompt="question", options={"temperature": 0})
        self.assertEqual(result.response, " answer ")
        body = client._http_request_json.call_args.kwargs["body"]
        self.assertFalse(body["stream"])
        self.assertEqual(body["options"], {"temperature": 0})

        client._http_request_json.return_value = {"embedding": [1, 2.5]}
        self.assertEqual(client.embed(model="embed", text="hello"), [1.0, 2.5])
        client._http_request_json.return_value = {"embeddings": [[3, 4]]}
        self.assertEqual(client.embed(model="embed", text="hello"), [3.0, 4.0])

        client._http_request_json.return_value = {"response": "ok"}
        result = client.generate_with_image(model="vision", prompt="describe", image=b"abc")
        self.assertEqual(result.response, "ok")
        image_body = client._http_request_json.call_args.kwargs["body"]
        self.assertEqual(image_body["images"], [base64.b64encode(b"abc").decode("ascii")])

    def test_invalid_response_and_image_type(self):
        client = OllamaWrapper()
        client._http_request_json = Mock(return_value={"response": 4})
        with self.assertRaises(OllamaResponseError):
            client.generate_text(model="llama", prompt="x")
        with self.assertRaises(TypeError):
            client.generate_with_image(model="vision", prompt="x", image=object())

    @patch("NaturSQL.ollama_client.ollama_wrapper_iut.shutil.which", return_value=None)
    def test_start_server_requires_ollama_executable(self, _which):
        with self.assertRaisesRegex(Exception, "introuvable"):
            OllamaWrapper().start_server()

    def test_llm_adapter_builds_prompt_and_strips_response(self):
        client = Mock()
        client.generate = AsyncMock(return_value="  SELECT 1;  ")
        result = asyncio.run(LLMClient(client).generate_sql("Combien ?", "TABLE details"))
        self.assertEqual(result, "SELECT 1;")
        prompt = client.generate.call_args.args[0]
        self.assertIn("Combien ?", prompt)
        self.assertIn("TABLE details", prompt)
        self.assertEqual(client.generate.call_args.kwargs["options"], {"temperature": 0})


if __name__ == "__main__":
    unittest.main()