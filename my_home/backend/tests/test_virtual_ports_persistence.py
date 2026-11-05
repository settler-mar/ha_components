import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from models import virtual_ports_routes


class VirtualPortsPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.temp_dir.name) / "virtual_ports.json"
        self.file_patch = patch.object(
            virtual_ports_routes, "get_virtual_ports_file", return_value=str(self.file_path)
        )
        self.file_patch.start()

    def tearDown(self):
        self.file_patch.stop()
        self.temp_dir.cleanup()

    def test_save_is_atomic_and_creates_valid_json(self):
        payload = {"ports": [{"id": "one", "value": 25}]}

        virtual_ports_routes.save_virtual_ports(payload)

        with self.file_path.open(encoding="utf-8") as file:
            self.assertEqual(json.load(file), payload)
        self.assertFalse(list(self.file_path.parent.glob(".virtual_ports.*.tmp")))

    def test_corrupt_active_file_is_restored_from_last_good_backup(self):
        first = {"ports": [{"id": "first"}]}
        second = {"ports": [{"id": "second"}]}
        virtual_ports_routes.save_virtual_ports(first)
        virtual_ports_routes.save_virtual_ports(second)

        self.file_path.write_text('{"ports": [', encoding="utf-8")

        self.assertEqual(virtual_ports_routes.load_virtual_ports(), first)
        with self.file_path.open(encoding="utf-8") as file:
            self.assertEqual(json.load(file), first)

    def test_concurrent_saves_never_leave_invalid_json(self):
        payloads = [{"ports": [{"id": str(index)}]} for index in range(20)]

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(virtual_ports_routes.save_virtual_ports, payloads))

        with self.file_path.open(encoding="utf-8") as file:
            result = json.load(file)
        self.assertIn(result, payloads)


if __name__ == "__main__":
    unittest.main()
