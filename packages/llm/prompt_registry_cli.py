from __future__ import annotations

import argparse

from packages.llm.prompt_registry import get_prompt_registry


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect and validate the local prompt registry.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List registered prompts and active versions.")

    show_parser = subparsers.add_parser("show", help="Show prompt metadata.")
    show_parser.add_argument("prompt_id")
    show_parser.add_argument("--version", default=None)
    show_parser.add_argument(
        "--show-templates",
        action="store_true",
        help="Include system and user templates in the output.",
    )

    versions_parser = subparsers.add_parser("versions", help="List known versions for a prompt.")
    versions_parser.add_argument("prompt_id")

    subparsers.add_parser("validate", help="Validate registry integrity.")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    registry = get_prompt_registry()

    if args.command == "list":
        for definition in registry.list_prompts():
            print(
                f"{definition.prompt_id} | active_version={definition.version} | "
                f"status={definition.status}"
            )
        return

    if args.command == "show":
        definition = (
            registry.get(args.prompt_id, args.version)
            if args.version is not None
            else registry.get_active(args.prompt_id)
        )
        print(f"prompt_id: {definition.prompt_id}")
        print(f"version: {definition.version}")
        print(f"name: {definition.name}")
        print(f"status: {definition.status}")
        print(f"description: {definition.description}")
        print(f"output_contract: {definition.output_contract}")
        print(f"input_variables: {', '.join(definition.input_variables)}")
        print(f"tags: {', '.join(definition.tags)}")
        print(f"created_at: {definition.created_at}")
        if args.show_templates:
            print(f"system_template: {definition.system_template}")
            print(f"user_template: {definition.user_template}")
        return

    if args.command == "versions":
        versions = registry.list_versions(args.prompt_id)
        print("\n".join(versions))
        return

    registry.validate()
    print("Prompt registry is valid.")


if __name__ == "__main__":
    main()
