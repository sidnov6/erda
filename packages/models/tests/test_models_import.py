import erda_models


def test_import() -> None:
    assert erda_models.__version__ == "0.1.0"
