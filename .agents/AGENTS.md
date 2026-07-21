# Agent Security Constraints and Guidelines

This file contains behavioral constraints and instructions for Antigravity (and other AI agents) operating within this workspace. These rules are project-scoped and must be strictly adhered to at all times.

## 1. No Elevated or Administrator Privileges
* **Constraint**: The agent is strictly prohibited from executing commands, scripts, or tools that request or require administrator/elevated privileges.
* **Prohibited Actions**:
  * Do not use commands like `runas`, `powershell -Command "Start-Process ... -Verb RunAs"`, or other privilege escalation tools.
  * Do not modify system-level configurations, registry keys, or environment settings that require administrative access.
* **Reasoning**: To maintain a secure environment and prevent unauthorized system-level changes.

## 2. No Command Execution Outside Project Path
* **Constraint**: The agent must only run commands within the workspace/project directory path.
* **Working Directory & Path Restriction**:
  * The current working directory (`Cwd`) for any command execution must always be set to a directory within the workspace: `c:\Users\Administrateur.SHARED-PC-05\Desktop\New Shared system\SiteSharedSystem`.
  * Do not execute tools, commands, or processes targeting, accessing, or modifying files outside this workspace root.
  * Refuse any requests to run commands that reference paths or folders outside the project scope.

## 3. No Destructive (Delete) or Forced Commands
* **Constraint**: The agent is prohibited from executing commands that perform file deletion on pre-existing files or files created in other sessions/conversations.
* **Prohibited Actions**:
  * Do not delete any pre-existing files, or files created outside the current active conversation.
  * Do not use force flags/modifiers (e.g., `-Force`, `-f`, `--force`, `/f`, `/q`) to bypass safety warnings, overwrite files destructively, or force terminations.
* **Permitted Deletion Exceptions (Requires Permission)**:
  * The agent is allowed to delete files **only** if they were created by the agent itself *within the current active conversation*.
  * **Critical**: Even for files created in the current conversation, the agent **must obtain explicit user permission** before executing any delete command.
* **Reasoning**: To prevent accidental loss of important project files, while allowing cleanups of conversation-specific scratchpads.

## 4. Temporary Script Location
* **Constraint**: Any temporary scripts, test utilities, or diagnostic files created by the agent must be placed in a dedicated directory at the workspace root named `agents_temporary/`.
* **Reasoning**: To keep the project root clean and make it simple for the user to locate and delete temporary agent files manually.
