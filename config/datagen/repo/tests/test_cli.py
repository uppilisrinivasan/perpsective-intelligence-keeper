from lamina.cli import main


def test_get(write, capsys):
    path = write("c.conf", "[a]\nx = 42\n")
    assert main(["get", path, "a.x"]) == 0
    assert capsys.readouterr().out.strip() == "42"


def test_get_missing_key(write):
    path = write("c.conf", "[a]\nx = 42\n")
    assert main(["get", path, "a.y"]) == 1


def test_check_reports_errors(write, capsys):
    path = write("c.conf", "[a\n")
    assert main(["check", path]) == 1
    assert "line 1" in capsys.readouterr().err


def test_usage():
    assert main([]) == 2
