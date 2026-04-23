from __future__ import annotations

import unittest

from src.manifest import build_command_manifest, build_commands


class ManifestCommandsTests(unittest.TestCase):
    def test_build_commands_has_stable_slash_names(self) -> None:
        names = {c.name for c in build_commands()}
        self.assertEqual(
            names,
            {
                "instance",
                "player-search",
                "subscribe",
                "subscription",
                "unsubscribe",
            },
        )

    def test_instance_command_has_raid_instance_id_option(self) -> None:
        cmds = {c.name: c for c in build_commands()}
        inst = cmds["instance"]
        self.assertIsNotNone(inst.options)
        opt_names = {o.name for o in (inst.options or [])}
        self.assertIn("raid_instance_id", opt_names)

    def test_subscribe_dm_permission_false(self) -> None:
        cmds = {c.name: c for c in build_commands()}
        self.assertIs(cmds["subscribe"].dm_permission, False)

    def test_manifest_json_serializable_shape(self) -> None:
        manifest = build_command_manifest()
        self.assertIsInstance(manifest, list)
        self.assertGreater(len(manifest), 0)
        first = manifest[0]
        self.assertIn("name", first)
        self.assertIn("type", first)
        self.assertIn("description", first)


if __name__ == "__main__":
    unittest.main()
