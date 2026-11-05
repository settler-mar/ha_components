import unittest
import asyncio
from datetime import datetime, timedelta, timezone

from utils.module_links import ModuleLink
from models.module_link_routes import dispatch_link_value


class ModuleLinkTests(unittest.TestCase):
    def make_link(self):
        return ModuleLink(
            link_id="test-link",
            producer="producer",
            consumer="consumer",
            values={
                "enable": {
                    "name": "enable",
                    "direction": "producer_to_consumer",
                    "value_type": "boolean",
                    "initial": False,
                    "on_stale": False,
                    "timeout_s": 120,
                },
                "supply": {
                    "name": "supply",
                    "direction": "producer_to_consumer",
                    "value_type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "initial": 25,
                    "on_stale": None,
                    "timeout_s": 120,
                },
            },
        )

    def test_restart_safe_default_mode(self):
        link = self.make_link()
        self.assertEqual(link.mode, "disabled")
        self.assertFalse(link.virtual["active"])

    def test_disabled_rejects_runtime_updates_at_route_boundary(self):
        link = self.make_link()
        link.values["ready"] = {
            "name": "ready",
            "direction": "consumer_to_producer",
            "value_type": "boolean",
            "initial": False,
            "on_stale": False,
            "timeout_s": 120,
        }
        link.__post_init__()
        self.assertEqual(link.mode, "disabled")
        link.set_mode("virtual")
        link.update("enable", True)
        link.update("supply", 42)
        self.assertTrue(link.virtual["active"])
        self.assertTrue(link.virtual["ready"])
        self.assertEqual(link.virtual["supply"], 42)
        self.assertEqual(link.states["ready"].value, True)
        self.assertEqual(link.states["ready"].quality, "good")
        self.assertEqual(link.states["supply"].value, 42)
        self.assertEqual(link.states["supply"].quality, "good")

    def test_virtual_boiler_times_out_its_feedback(self):
        link = self.make_link()
        link.values["ready"] = {
            "name": "ready",
            "direction": "consumer_to_producer",
            "value_type": "boolean",
            "initial": False,
            "on_stale": False,
            "timeout_s": 120,
        }
        link.values["supply"] = {
            "name": "supply",
            "direction": "consumer_to_producer",
            "value_type": "number",
            "initial": None,
            "on_stale": None,
            "timeout_s": 120,
        }
        link.__post_init__()
        link.virtual["timeout_s"] = 1
        link.set_mode("virtual")
        link.update("enable", True)
        link.virtual["last_update"] = (datetime.now(timezone.utc) - timedelta(seconds=3)).isoformat()
        link.tick()
        self.assertFalse(link.virtual["ready"])
        self.assertIsNone(link.virtual["supply"])
        self.assertEqual(link.states["ready"].quality, "timeout")

    def test_invalid_range_is_fail_closed(self):
        link = self.make_link()
        link.set_mode("virtual")
        link.update("supply", 101)
        self.assertEqual(link.states["supply"].quality, "invalid")
        self.assertIsNone(link.states["supply"].value)

    def test_virtual_mode_cannot_expose_physical_output(self):
        link = self.make_link()
        self.assertTrue(link.to_dict()["physical_outputs_protected"])

    def test_timeout_is_explicit_and_falls_back(self):
        link = self.make_link()
        link.values["supply"].timeout_s = 1
        link.update("supply", 42)
        link.states["supply"].updated_at = (datetime.now(timezone.utc) - timedelta(seconds=3)).isoformat()
        link.tick()
        self.assertEqual(link.states["supply"].quality, "timeout")
        self.assertIsNone(link.states["supply"].value)

    def test_value_contract_exposes_system_endpoints_and_ha_binding(self):
        link = self.make_link()
        link.values["enable"].source = {"system": "home_assistant", "module": "floor_heating"}
        link.values["enable"].target = {"system": "esp", "module": "boiler_ctrl"}
        link.values["enable"].ha_binding = {"mode": "ha_entity", "entity_id": "input_boolean.boiler_enable"}
        value = link.to_dict()["values"]["enable"]
        self.assertEqual(value["source"]["system"], "home_assistant")
        self.assertEqual(value["target"]["system"], "esp")
        self.assertEqual(value["ha_binding"]["mode"], "ha_entity")

    def test_physical_binding_is_explicit_and_fail_closed(self):
        link = self.make_link()
        link.values["enable"].physical_binding = {"device_id": 1, "port_id": "relay_1"}
        self.assertEqual(link.to_dict()["values"]["enable"]["physical_binding"]["port_id"], "relay_1")
        self.assertEqual(asyncio.run(dispatch_link_value(link, "enable", True))["status"], "not_physical")
        link.set_mode("physical")
        link.values["supply"].physical_binding = {}
        result = asyncio.run(dispatch_link_value(link, "supply", 42))
        self.assertEqual(result["status"], "not_configured")


if __name__ == "__main__":
    unittest.main()
