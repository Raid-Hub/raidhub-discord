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
                "search",
                "subscribe",
                "subscriptions",
                "unsubscribe",
            },
        )

    def test_search_command_has_search_query_option(self) -> None:
        cmds = {c.name: c for c in build_commands()}
        search = cmds["search"]
        self.assertIsNotNone(search.options)
        opt_names = {o.name for o in (search.options or [])}
        self.assertIn("search_query", opt_names)

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
            player_opt_names, {"player", "require_fresh", "require_completed"}
        )
        self.assertEqual(
            clan_opt_names,
            {"clan", "require_fresh", "require_completed"},
        )
        player_rq = next(
            o for o in (options["player"].options or []) if o.name == "require_fresh"
        )
        clan_rq = next(
            o for o in (options["clan"].options or []) if o.name == "require_fresh"
        )
        self.assertEqual(player_rq.type, CommandOptionType.BOOLEAN)
        self.assertEqual(clan_rq.type, CommandOptionType.BOOLEAN)

    def test_unsubscribe_has_all_player_clan_subcommands(self) -> None:
        cmds = {c.name: c for c in build_commands()}
        unsub = cmds["unsubscribe"]
        self.assertIsNotNone(unsub.options)
        option_names = {o.name for o in (unsub.options or [])}
        self.assertEqual(option_names, {"all", "player", "clan"})

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
