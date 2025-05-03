try:
    import playwright

    pytest_plugins = "tdom.fixtures"
except ImportError:
    pass
