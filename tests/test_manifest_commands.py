from __future__ import annotations

import unittest

from src.manifest import build_command_manifest, build_commands
from src.manifest.schema import CommandOptionType


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

    def test_subscribe_subcommands_expose_rule_filter_options(self) -> None:
        cmds = {c.name: c for c in build_commands()}
        subscribe = cmds["subscribe"]
        options = {o.name: o for o in (subscribe.options or [])}
        player_opt_names = {o.name for o in (options["player"].options or [])}
        clan_opt_names = {o.name for o in (options["clan"].options or [])}
        self.assertEqual(
            player_opt_names, {"player", "require_fresh", "require_completed", "raid"}
        )
        self.assertEqual(
            clan_opt_names,
            {"clan", "require_fresh", "require_completed", "raid"},
        )
        player_raid = next(
            o for o in (options["player"].options or []) if o.name == "raid"
        )
        clan_raid = next(o for o in (options["clan"].options or []) if o.name == "raid")
        self.assertEqual(player_raid.type, CommandOptionType.INTEGER)
        self.assertEqual(clan_raid.type, CommandOptionType.INTEGER)

    def test_unsubscribe_has_player_and_clan_subcommands(self) -> None:
        cmds = {c.name: c for c in build_commands()}
        unsub = cmds["unsubscribe"]
        self.assertIsNotNone(unsub.options)
        option_names = {o.name for o in (unsub.options or [])}
        self.assertEqual(option_names, {"delete", "player", "clan"})

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
