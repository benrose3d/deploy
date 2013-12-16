import os


def main():
    from fabric.main import main
    main([os.path.dirname(__file__)])


if __name__ == "__main__":
    main()
