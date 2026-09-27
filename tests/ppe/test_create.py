"""Tests for ppe CLI scaffold and env create (Phase 1)."""

# ---------------------------------------------------------------------------
# CLI scaffold tests
# ---------------------------------------------------------------------------


class TestParser:
    """Tests for the argparse parser structure."""

    def test_main_no_command_prints_help(self, capsys):
        from nb_wrangler.ppe.cli import main

        rc = main([])
        assert rc == 0
        out = capsys.readouterr()
        assert "env" in out.out
        assert "var" in out.out
        assert "data" in out.out
        assert "export" in out.out
        assert "status" in out.out
        assert "doctor" in out.out

    def test_parses_env_create(self):
        from nb_wrangler.ppe.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["env", "create", "--from-empty", "--name", "demo", "--python", "3.11"]
        )
        assert args.command == "env"
        assert args.env_command == "create"
        assert args.name == "demo"
        assert args.python == "3.11"
        assert args.from_empty is True

    def test_create_requires_name(self):
        from nb_wrangler.ppe.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(["env", "create", "--from-empty"])
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for missing --name")

    def test_create_mutually_exclusive_sources(self):
        from nb_wrangler.ppe.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(
                [
                    "env",
                    "create",
                    "--from-empty",
                    "--from-requirements",
                    "req.txt",
                    "--name",
                    "x",
                ]
            )
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for conflicting seed sources")

    def test_create_requires_one_source(self):
        from nb_wrangler.ppe.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(["env", "create", "--name", "x"])
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for no seed source")


# ---------------------------------------------------------------------------
# Not-implemented stub tests
# ---------------------------------------------------------------------------


class TestNotImplemented:
    """All non-create subcommands should exit 2 cleanly."""

    def test_var_ls_not_implemented(self, capsys):
        from nb_wrangler.ppe.cli import main

        rc = main(["var", "ls"])
        assert rc == 2

    def test_data_ls_not_implemented(self, capsys):
        from nb_wrangler.ppe.cli import main

        rc = main(["data", "ls"])
        assert rc == 2

    def test_status_not_implemented(self, capsys):
        from nb_wrangler.ppe.cli import main

        rc = main(["status"])
        assert rc == 2

    def test_doctor_not_implemented(self, capsys):
        from nb_wrangler.ppe.cli import main

        rc = main(["doctor"])
        assert rc == 2

    def test_env_no_subcommand_prints_help(self, capsys):
        from nb_wrangler.ppe.cli import main

        rc = main(["env"])
        assert rc == 0  # prints help
