"""Allow ``python -m audioatlas ...`` as an alternative to the installed
console script. Useful when running from a source checkout without
``pip install -e .``."""

from audioatlas.cli import main

if __name__ == "__main__":
    main()
