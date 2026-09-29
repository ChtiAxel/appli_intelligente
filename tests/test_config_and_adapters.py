import os
import unittest
from unittest.mock import Mock, patch

from NaturSQL.ollama_client.embedding import EmbeddingClient
from NaturSQL.ollama_client.vlm import VLMClient
from NaturSQL import config


class ConfigAndAdapterTests(unittest.TestCase):
    def test_config_defaults_and_required_values_are_loaded(self):
        self.assertTrue(config.OLLAMA_BASE_URL)
        self.assertTrue(config.OLLAMA_MODEL)
        self.assertIsInstance(config.DB_PORT, int)

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "MISSING"):
                config._require("MISSING")

    def test_embedding_and_vlm_adapters_keep_injected_client(self):
        client = Mock()
        self.assertIs(EmbeddingClient(client).client, client)
        self.assertIs(VLMClient(client).client, client)


if __name__ == "__main__":
    unittest.main()