import argparse
import sys
import io
import contextlib
from typing import List, Dict, Any, Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, OptionList, Static, Log, Input, Button, Label, Select
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual import work

from textual.screen import ModalScreen
from textual.containers import Grid
from contracthub.interfaces.cli import _build_parser, main as cli_main

class InitConfigModal(ModalScreen[bool]):
    CSS = """
    InitConfigModal {
        align: center middle;
    }
    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 0 1;
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
    }
    #question {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }
    Button {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("No configuration file found.\\nWould you like to generate a default .contracthub.yaml?", id="question"),
            Button("Yes, generate it", variant="primary", id="yes"),
            Button("No, maybe later", variant="error", id="no"),
            id="dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

class DynamicForm(Container):
    """A dynamically generated form based on argparse arguments."""

    def __init__(self, parser: argparse.ArgumentParser, command_name: str):
        super().__init__()
        self.parser = parser
        self.command_name = command_name
        self.fields: Dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        yield Label(f"Command: {self.command_name}", classes="form-title")
        yield Static("Fill in the arguments below:", classes="form-subtitle")

        for action in self.parser._actions:
            # Skip help and common ignored options
            if action.dest == "help" or action.dest == "command":
                continue

            field_id = f"field_{action.dest}"
            label_text = f"{action.dest}"
            if action.required:
                label_text += " (*)"

            yield Label(label_text)

            if action.choices:
                # Provide a Select for choices
                options = [(str(c), str(c)) for c in action.choices]
                default_val = str(action.default) if action.default is not None and str(action.default) in action.choices else Select.BLANK
                select = Select(options, id=field_id, prompt="Select an option", value=default_val)
                self.fields[action.dest] = select
                yield select
            elif action.nargs == 0 or isinstance(action, argparse._StoreTrueAction):
                # For boolean flags, a Select with Yes/No or a custom switch. Use Select for simplicity
                select = Select([("True", "True"), ("False", "False")], id=field_id, prompt="False")
                self.fields[action.dest] = select
                yield select
            else:
                # Regular text input
                default_val = str(action.default) if action.default is not None and action.default != argparse.SUPPRESS else ""
                input_widget = Input(placeholder=action.help or "", id=field_id, value=default_val)
                self.fields[action.dest] = input_widget
                yield input_widget

        yield Button("Execute", id="execute-btn", variant="primary")

    def build_args_list(self) -> List[str]:
        args_list = [self.command_name]
        for dest, widget in self.fields.items():
            action = next((a for a in self.parser._actions if a.dest == dest), None)
            if not action:
                continue

            value = None
            if isinstance(widget, Input):
                value = widget.value
            elif isinstance(widget, Select):
                value = widget.value

            if value and value != Select.BLANK:
                if isinstance(action, argparse._StoreTrueAction):
                    if value == "True":
                        args_list.append(action.option_strings[0])
                else:
                    if action.option_strings:
                        args_list.append(action.option_strings[0])
                    args_list.append(str(value))
        return args_list


class ContractHubTUI(App):
    """A Textual App to navigate and execute contracthub commands."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #main-container {
        height: 1fr;
        layout: horizontal;
    }
    #sidebar {
        width: 25;
        dock: left;
        border-right: solid green;
    }
    #content-area {
        width: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }
    #log-panel {
        height: 10;
        border-top: solid green;
        dock: bottom;
        background: $surface-darken-1;
    }
    .form-title {
        text-style: bold;
        padding-bottom: 1;
        color: $accent;
    }
    .form-subtitle {
        padding-bottom: 1;
    }
    Button {
        margin-top: 2;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.cli_parser = _build_parser()
        self.subparsers = self._extract_subparsers()
        self.commands = [cmd for cmd in self.subparsers.keys() if cmd not in ("enrich", "tui")]

    def _extract_subparsers(self) -> Dict[str, argparse.ArgumentParser]:
        for action in self.cli_parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action.choices
        return {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            # Sidebar for commands
            yield OptionList(*[Option(cmd, id=cmd) for cmd in self.commands], id="sidebar")

            # Main content area
            yield Vertical(id="content-area")

        yield Log(id="log-panel", highlight=True)
        yield Footer()

    def on_mount(self) -> None:
        from contracthub.core.config import config_manager
        
        def handle_init(result: bool) -> None:
            if result:
                import argparse
                from contracthub.interfaces.cli import _run_init
                _run_init(argparse.Namespace())
                config_manager._load_configs()
                
            if self.commands:
                self.load_command_form(self.commands[0])

        if not config_manager.config_data:
            self.push_screen(InitConfigModal(), handle_init)
        else:
            if self.commands:
                self.load_command_form(self.commands[0])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        command_name = event.option.id
        self.load_command_form(command_name)

    def load_command_form(self, command_name: str) -> None:
        content_area = self.query_one("#content-area")
        content_area.remove_children()

        parser = self.subparsers.get(command_name)
        if parser:
            content_area.mount(DynamicForm(parser, command_name))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "execute-btn":
            form = event.button.parent
            if isinstance(form, DynamicForm):
                args_list = form.build_args_list()
                self.execute_command(args_list)

    @work(thread=True)
    def execute_command(self, args_list: List[str]) -> None:
        log_panel = self.query_one("#log-panel", Log)
        self.call_from_thread(log_panel.write_line, f"> contracthub {' '.join(args_list)}")

        # Capture stdout and stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        original_argv = sys.argv.copy()
        sys.argv = ["contracthub"] + args_list

        try:
            # We run cli_main which returns an exit code
            exit_code = cli_main()
            stdout_str = sys.stdout.getvalue()
            stderr_str = sys.stderr.getvalue()

            if stdout_str:
                self.call_from_thread(log_panel.write_line, stdout_str)
            if stderr_str:
                self.call_from_thread(log_panel.write_line, f"ERR: {stderr_str}")
            self.call_from_thread(log_panel.write_line, f"Exited with code: {exit_code}\n")
        except Exception as e:
            self.call_from_thread(log_panel.write_line, f"Exception: {e}\n")
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            sys.argv = original_argv

if __name__ == "__main__":
    app = ContractHubTUI()
    app.run()
