# BalatroBot API

This page provides comprehensive API documentation for the BalatroBot Python framework. The API enables you to build automated bots that interact with the Balatro card game through a structured TCP communication protocol.

The API is organized into several key components: the `BalatroClient` for managing game connections and sending commands, enums that define game states and actions, exception classes for robust error handling, and data models that structure requests and responses between your bot and the game.

## Client

The `BalatroClient` is the main interface for communicating with the Balatro game through TCP connections. It handles connection management, message serialization, and error handling.

### `balatrobot.client.BalatroClient`

Client for communicating with the BalatroBot game API.

The client provides methods for game control, state management, and development tools including a checkpointing system for saving and loading game states.

Attributes:

| Name          | Type     | Description                 |
| ------------- | -------- | --------------------------- |
| `host`        |          | Host address to connect to  |
| `port`        |          | Port number to connect to   |
| `timeout`     |          | Socket timeout in seconds   |
| `buffer_size` |          | Socket buffer size in bytes |
| `_socket`     | \`socket | None\`                      |

Source code in `src/balatrobot/client.py`

````python
class BalatroClient:
    """Client for communicating with the BalatroBot game API.

    The client provides methods for game control, state management, and development tools
    including a checkpointing system for saving and loading game states.

    Attributes:
        host: Host address to connect to
        port: Port number to connect to
        timeout: Socket timeout in seconds
        buffer_size: Socket buffer size in bytes
        _socket: Socket connection to BalatroBot
    """

    host = "127.0.0.1"
    timeout = 60.0
    buffer_size = 65536

    def __init__(self, port: int = 12346):
        """Initialize BalatroBot client

        Args:
            port: Port number to connect to (default: 12346)
        """
        self.port = port
        self._socket: socket.socket | None = None
        self._connected = False
        self._message_buffer = b""  # Buffer for incomplete messages

    def _receive_complete_message(self) -> bytes:
        """Receive a complete message from the socket, handling message boundaries properly."""
        if not self._connected or not self._socket:
            raise ConnectionFailedError(
                "Socket not connected",
                error_code="E008",
                context={
                    "connected": self._connected,
                    "socket": self._socket is not None,
                },
            )

        # Check if we already have a complete message in the buffer
        while b"\n" not in self._message_buffer:
            try:
                chunk = self._socket.recv(self.buffer_size)
            except socket.timeout:
                raise ConnectionFailedError(
                    "Socket timeout while receiving data",
                    error_code="E008",
                    context={
                        "timeout": self.timeout,
                        "buffer_size": len(self._message_buffer),
                    },
                )
            except socket.error as e:
                raise ConnectionFailedError(
                    f"Socket error while receiving: {e}",
                    error_code="E008",
                    context={"error": str(e), "buffer_size": len(self._message_buffer)},
                )

            if not chunk:
                raise ConnectionFailedError(
                    "Connection closed by server",
                    error_code="E008",
                    context={"buffer_size": len(self._message_buffer)},
                )
            self._message_buffer += chunk

        # Extract the first complete message
        message_end = self._message_buffer.find(b"\n")
        complete_message = self._message_buffer[:message_end]

        # Update buffer to remove the processed message
        remaining_data = self._message_buffer[message_end + 1 :]
        self._message_buffer = remaining_data

        # Log any remaining data for debugging
        if remaining_data:
            logger.warning(f"Data remaining in buffer: {len(remaining_data)} bytes")
            logger.debug(f"Buffer preview: {remaining_data[:100]}...")

        return complete_message

    def __enter__(self) -> Self:
        """Enter context manager and connect to the game."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and disconnect from the game."""
        self.disconnect()

    def connect(self) -> None:
        """Connect to Balatro TCP server

        Raises:
            ConnectionFailedError: If not connected to the game
        """
        if self._connected:
            return

        logger.info(f"Connecting to BalatroBot API at {self.host}:{self.port}")
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_RCVBUF, self.buffer_size
            )
            self._socket.connect((self.host, self.port))
            self._connected = True
            logger.info(
                f"Successfully connected to BalatroBot API at {self.host}:{self.port}"
            )
        except (socket.error, OSError) as e:
            logger.error(f"Failed to connect to {self.host}:{self.port}: {e}")
            raise ConnectionFailedError(
                f"Failed to connect to {self.host}:{self.port}",
                error_code="E008",
                context={"host": self.host, "port": self.port, "error": str(e)},
            ) from e

    def disconnect(self) -> None:
        """Disconnect from the BalatroBot game API."""
        if self._socket:
            logger.info(f"Disconnecting from BalatroBot API at {self.host}:{self.port}")
            self._socket.close()
            self._socket = None
        self._connected = False
        # Clear message buffer on disconnect
        self._message_buffer = b""

    def send_message(self, name: str, arguments: dict | None = None) -> dict:
        """Send JSON message to Balatro and receive response

        Args:
            name: Function name to call
            arguments: Function arguments

        Returns:
            Response from the game API

        Raises:
            ConnectionFailedError: If not connected to the game
            BalatroError: If the API returns an error
        """
        if arguments is None:
            arguments = {}

        if not self._connected or not self._socket:
            raise ConnectionFailedError(
                "Not connected to the game API",
                error_code="E008",
                context={
                    "connected": self._connected,
                    "socket": self._socket is not None,
                },
            )

        # Create and validate request
        request = APIRequest(name=name, arguments=arguments)
        logger.debug(f"Sending API request: {name}")

        try:
            # Send request
            message = request.model_dump_json() + "\n"
            self._socket.send(message.encode())

            # Receive response using improved message handling
            complete_message = self._receive_complete_message()

            # Decode and validate the message
            message_str = complete_message.decode().strip()
            logger.debug(f"Raw message length: {len(message_str)} characters")
            logger.debug(f"Message preview: {message_str[:100]}...")

            # Ensure the message is properly formatted JSON
            if not message_str:
                raise BalatroError(
                    "Empty response received from game",
                    error_code="E001",
                    context={"raw_data_length": len(complete_message)},
                )

            response_data = json.loads(message_str)

            # Check for error response
            if "error" in response_data:
                logger.error(f"API request {name} failed: {response_data.get('error')}")
                raise create_exception_from_error_response(response_data)

            logger.debug(f"API request {name} completed successfully")
            return response_data

        except socket.error as e:
            logger.error(f"Socket error during API request {name}: {e}")
            raise ConnectionFailedError(
                f"Socket error during communication: {e}",
                error_code="E008",
                context={"error": str(e)},
            ) from e
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from API request {name}: {e}")
            logger.error(f"Problematic message content: {message_str[:200]}...")
            logger.error(
                f"Message buffer state: {len(self._message_buffer)} bytes remaining"
            )

            # Clear the message buffer to prevent cascading errors
            if self._message_buffer:
                logger.warning("Clearing message buffer due to JSON parse error")
                self._message_buffer = b""

            raise BalatroError(
                f"Invalid JSON response from game: {e}",
                error_code="E001",
                context={"error": str(e), "message_preview": message_str[:100]},
            ) from e

    # Checkpoint Management Methods

    def _convert_windows_path_to_linux(self, windows_path: str) -> str:
        """Convert Windows path to Linux Steam Proton path if on Linux.

        Args:
            windows_path: Windows-style path (e.g., "C:/Users/.../Balatro/3/save.jkr")

        Returns:
            Converted path for Linux or original path for other platforms
        """

        if platform.system() == "Linux":
            # Match Windows drive letter and path (e.g., "C:/...", "D:\\...", "E:...")
            match = re.match(r"^([A-Z]):[\\/]*(.*)", windows_path, re.IGNORECASE)
            if match:
                # Replace drive letter with Linux Steam Proton prefix
                linux_prefix = str(
                    Path(
                        "~/.steam/steam/steamapps/compatdata/2379780/pfx/drive_c"
                    ).expanduser()
                )
                # Normalize slashes and join with prefix
                rest_of_path = match.group(2).replace("\\", "/")
                return linux_prefix + "/" + rest_of_path

        return windows_path

    def get_save_info(self) -> dict:
        """Get the current save file location and profile information.

        Development tool for working with save files and checkpoints.

        Returns:
            Dictionary containing:
            - profile_path: Current profile path (e.g., "3")
            - save_directory: Full path to Love2D save directory
            - save_file_path: Full OS-specific path to save.jkr file
            - has_active_run: Whether a run is currently active
            - save_exists: Whether the save file exists

        Raises:
            BalatroError: If request fails

        Note:
            This is primarily for development and testing purposes.
        """
        save_info = self.send_message("get_save_info")

        # Convert Windows paths to Linux Steam Proton paths if needed
        if "save_file_path" in save_info and save_info["save_file_path"]:
            save_info["save_file_path"] = self._convert_windows_path_to_linux(
                save_info["save_file_path"]
            )
        if "save_directory" in save_info and save_info["save_directory"]:
            save_info["save_directory"] = self._convert_windows_path_to_linux(
                save_info["save_directory"]
            )

        return save_info

    def save_checkpoint(self, checkpoint_name: str | Path) -> Path:
        """Save the current save.jkr file as a checkpoint.

        Args:
            checkpoint_name: Either:
                - A checkpoint name (saved to checkpoints dir)
                - A full file path where the checkpoint should be saved
                - A directory path (checkpoint will be saved as 'save.jkr' inside it)

        Returns:
            Path to the saved checkpoint file

        Raises:
            BalatroError: If no save file exists or the destination path is invalid
            IOError: If file operations fail
        """
        # Get current save info
        save_info = self.get_save_info()
        if not save_info.get("save_exists"):
            raise BalatroError(
                "No save file exists to checkpoint", ErrorCode.INVALID_GAME_STATE
            )

        # Get the full save file path from API (already OS-specific)
        save_path = Path(save_info["save_file_path"])
        if not save_path.exists():
            raise BalatroError(
                f"Save file not found: {save_path}", ErrorCode.MISSING_GAME_OBJECT
            )

        # Normalize and interpret destination
        dest = Path(checkpoint_name).expanduser()
        # Treat paths without a .jkr suffix as directories
        if dest.suffix.lower() != ".jkr":
            raise BalatroError(
                f"Invalid checkpoint path provided: {dest}",
                ErrorCode.INVALID_PARAMETER,
                context={"path": str(dest), "reason": "Path does not end with .jkr"},
            )

        # Ensure destination directory exists
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise BalatroError(
                f"Invalid checkpoint path provided: {dest}",
                ErrorCode.INVALID_PARAMETER,
                context={"path": str(dest), "reason": str(e)},
            ) from e

        # Copy save file to checkpoint
        try:
            shutil.copy2(save_path, dest)
        except OSError as e:
            raise BalatroError(
                f"Failed to write checkpoint to: {dest}",
                ErrorCode.INVALID_PARAMETER,
                context={"path": str(dest), "reason": str(e)},
            ) from e

        return dest

    def prepare_save(self, source_path: str | Path) -> str:
        """Prepare a test save file for use with load_save.

        This copies a .jkr file from your test directory into Love2D's save directory
        in a temporary profile so it can be loaded with load_save().

        Args:
            source_path: Path to the .jkr save file to prepare

        Returns:
            The Love2D-relative path to use with load_save()
            (e.g., "checkpoint/save.jkr")

        Raises:
            BalatroError: If source file not found
            IOError: If file operations fail
        """
        source = Path(source_path)
        if not source.exists():
            raise BalatroError(
                f"Source save file not found: {source}", ErrorCode.MISSING_GAME_OBJECT
            )

        # Get save directory info
        save_info = self.get_save_info()
        if not save_info.get("save_directory"):
            raise BalatroError(
                "Cannot determine Love2D save directory", ErrorCode.INVALID_GAME_STATE
            )

        checkpoints_profile = "checkpoint"
        save_dir = Path(save_info["save_directory"])
        checkpoints_dir = save_dir / checkpoints_profile
        checkpoints_dir.mkdir(parents=True, exist_ok=True)

        # Copy the save file to the test profile
        dest_path = checkpoints_dir / "save.jkr"
        shutil.copy2(source, dest_path)

        # Return the Love2D-relative path
        return f"{checkpoints_profile}/save.jkr"

    def load_save(self, save_path: str | Path) -> dict:
        """Load a save file directly without requiring a game restart.

        This method loads a save file (in Love2D's save directory format) and starts
        a run from that save state. Unlike load_checkpoint which copies to the profile's
        save location and requires restart, this directly loads the save into the game.

        This is particularly useful for testing as it allows you to quickly jump to
        specific game states without manual setup.

        Args:
            save_path: Path to the save file relative to Love2D save directory
                      (e.g., "3/save.jkr" for profile 3's save)

        Returns:
            Game state after loading the save

        Raises:
            BalatroError: If save file not found or loading fails

        Note:
            This is a development tool that bypasses normal game flow.
            Use with caution in production bots.

        Example:
            ```python
            # Load a profile's save directly
            game_state = client.load_save("3/save.jkr")

            # Or use with prepare_save for external files
            save_path = client.prepare_save("tests/fixtures/shop_state.jkr")
            game_state = client.load_save(save_path)
            ```
        """
        # Convert to string if Path object
        if isinstance(save_path, Path):
            save_path = str(save_path)

        # Send load_save request to API
        return self.send_message("load_save", {"save_path": save_path})

    def load_absolute_save(self, save_path: str | Path) -> dict:
        """Load a save from an absolute path. Takes a full path from the OS as a .jkr file and loads it into the game.

        Args:
            save_path: Path to the save file relative to Love2D save directory
                      (e.g., "3/save.jkr" for profile 3's save)

        Returns:
            Game state after loading the save
        """
        love_save_path = self.prepare_save(save_path)
        return self.load_save(love_save_path)

    def screenshot(self, path: Path | None = None) -> Path:
        """
        Take a screenshot and save as both PNG and JPEG formats.

        Args:
            path: Optional path for PNG file. If provided, PNG will be moved to this location.

        Returns:
            Path to the PNG screenshot. JPEG is saved alongside with .jpg extension.

        Note:
            The response now includes both 'path' (PNG) and 'jpeg_path' (JPEG) keys.
            This method maintains backward compatibility by returning the PNG path.
        """
        screenshot_response = self.send_message("screenshot", {})

        if path is None:
            return Path(screenshot_response["path"])
        else:
            source_path = Path(screenshot_response["path"])
            dest_path = path
            shutil.move(source_path, dest_path)
            return dest_path

````

#### `connect()`

Connect to Balatro TCP server

Raises:

| Type                    | Description                  |
| ----------------------- | ---------------------------- |
| `ConnectionFailedError` | If not connected to the game |

Source code in `src/balatrobot/client.py`

```python
def connect(self) -> None:
    """Connect to Balatro TCP server

    Raises:
        ConnectionFailedError: If not connected to the game
    """
    if self._connected:
        return

    logger.info(f"Connecting to BalatroBot API at {self.host}:{self.port}")
    try:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(self.timeout)
        self._socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, self.buffer_size
        )
        self._socket.connect((self.host, self.port))
        self._connected = True
        logger.info(
            f"Successfully connected to BalatroBot API at {self.host}:{self.port}"
        )
    except (socket.error, OSError) as e:
        logger.error(f"Failed to connect to {self.host}:{self.port}: {e}")
        raise ConnectionFailedError(
            f"Failed to connect to {self.host}:{self.port}",
            error_code="E008",
            context={"host": self.host, "port": self.port, "error": str(e)},
        ) from e

```

#### `disconnect()`

Disconnect from the BalatroBot game API.

Source code in `src/balatrobot/client.py`

```python
def disconnect(self) -> None:
    """Disconnect from the BalatroBot game API."""
    if self._socket:
        logger.info(f"Disconnecting from BalatroBot API at {self.host}:{self.port}")
        self._socket.close()
        self._socket = None
    self._connected = False
    # Clear message buffer on disconnect
    self._message_buffer = b""

```

#### `get_save_info()`

Get the current save file location and profile information.

Development tool for working with save files and checkpoints.

Returns:

| Type   | Description                                            |
| ------ | ------------------------------------------------------ |
| `dict` | Dictionary containing:                                 |
| `dict` | profile_path: Current profile path (e.g., "3")         |
| `dict` | save_directory: Full path to Love2D save directory     |
| `dict` | save_file_path: Full OS-specific path to save.jkr file |
| `dict` | has_active_run: Whether a run is currently active      |
| `dict` | save_exists: Whether the save file exists              |

Raises:

| Type           | Description      |
| -------------- | ---------------- |
| `BalatroError` | If request fails |

Note

This is primarily for development and testing purposes.

Source code in `src/balatrobot/client.py`

```python
def get_save_info(self) -> dict:
    """Get the current save file location and profile information.

    Development tool for working with save files and checkpoints.

    Returns:
        Dictionary containing:
        - profile_path: Current profile path (e.g., "3")
        - save_directory: Full path to Love2D save directory
        - save_file_path: Full OS-specific path to save.jkr file
        - has_active_run: Whether a run is currently active
        - save_exists: Whether the save file exists

    Raises:
        BalatroError: If request fails

    Note:
        This is primarily for development and testing purposes.
    """
    save_info = self.send_message("get_save_info")

    # Convert Windows paths to Linux Steam Proton paths if needed
    if "save_file_path" in save_info and save_info["save_file_path"]:
        save_info["save_file_path"] = self._convert_windows_path_to_linux(
            save_info["save_file_path"]
        )
    if "save_directory" in save_info and save_info["save_directory"]:
        save_info["save_directory"] = self._convert_windows_path_to_linux(
            save_info["save_directory"]
        )

    return save_info

```

#### `load_absolute_save(save_path)`

Load a save from an absolute path. Takes a full path from the OS as a .jkr file and loads it into the game.

Parameters:

| Name        | Type  | Description | Default                                                                                           |
| ----------- | ----- | ----------- | ------------------------------------------------------------------------------------------------- |
| `save_path` | \`str | Path\`      | Path to the save file relative to Love2D save directory (e.g., "3/save.jkr" for profile 3's save) |

Returns:

| Type   | Description                       |
| ------ | --------------------------------- |
| `dict` | Game state after loading the save |

Source code in `src/balatrobot/client.py`

```python
def load_absolute_save(self, save_path: str | Path) -> dict:
    """Load a save from an absolute path. Takes a full path from the OS as a .jkr file and loads it into the game.

    Args:
        save_path: Path to the save file relative to Love2D save directory
                  (e.g., "3/save.jkr" for profile 3's save)

    Returns:
        Game state after loading the save
    """
    love_save_path = self.prepare_save(save_path)
    return self.load_save(love_save_path)

```

#### `load_save(save_path)`

Load a save file directly without requiring a game restart.

This method loads a save file (in Love2D's save directory format) and starts a run from that save state. Unlike load_checkpoint which copies to the profile's save location and requires restart, this directly loads the save into the game.

This is particularly useful for testing as it allows you to quickly jump to specific game states without manual setup.

Parameters:

| Name        | Type  | Description | Default                                                                                           |
| ----------- | ----- | ----------- | ------------------------------------------------------------------------------------------------- |
| `save_path` | \`str | Path\`      | Path to the save file relative to Love2D save directory (e.g., "3/save.jkr" for profile 3's save) |

Returns:

| Type   | Description                       |
| ------ | --------------------------------- |
| `dict` | Game state after loading the save |

Raises:

| Type           | Description                             |
| -------------- | --------------------------------------- |
| `BalatroError` | If save file not found or loading fails |

Note

This is a development tool that bypasses normal game flow. Use with caution in production bots.

Example

```python
# Load a profile's save directly
game_state = client.load_save("3/save.jkr")

# Or use with prepare_save for external files
save_path = client.prepare_save("tests/fixtures/shop_state.jkr")
game_state = client.load_save(save_path)

```

Source code in `src/balatrobot/client.py`

````python
def load_save(self, save_path: str | Path) -> dict:
    """Load a save file directly without requiring a game restart.

    This method loads a save file (in Love2D's save directory format) and starts
    a run from that save state. Unlike load_checkpoint which copies to the profile's
    save location and requires restart, this directly loads the save into the game.

    This is particularly useful for testing as it allows you to quickly jump to
    specific game states without manual setup.

    Args:
        save_path: Path to the save file relative to Love2D save directory
                  (e.g., "3/save.jkr" for profile 3's save)

    Returns:
        Game state after loading the save

    Raises:
        BalatroError: If save file not found or loading fails

    Note:
        This is a development tool that bypasses normal game flow.
        Use with caution in production bots.

    Example:
        ```python
        # Load a profile's save directly
        game_state = client.load_save("3/save.jkr")

        # Or use with prepare_save for external files
        save_path = client.prepare_save("tests/fixtures/shop_state.jkr")
        game_state = client.load_save(save_path)
        ```
    """
    # Convert to string if Path object
    if isinstance(save_path, Path):
        save_path = str(save_path)

    # Send load_save request to API
    return self.send_message("load_save", {"save_path": save_path})

````

#### `prepare_save(source_path)`

Prepare a test save file for use with load_save.

This copies a .jkr file from your test directory into Love2D's save directory in a temporary profile so it can be loaded with load_save().

Parameters:

| Name          | Type  | Description | Default                               |
| ------------- | ----- | ----------- | ------------------------------------- |
| `source_path` | \`str | Path\`      | Path to the .jkr save file to prepare |

Returns:

| Type  | Description                                      |
| ----- | ------------------------------------------------ |
| `str` | The Love2D-relative path to use with load_save() |
| `str` | (e.g., "checkpoint/save.jkr")                    |

Raises:

| Type           | Description              |
| -------------- | ------------------------ |
| `BalatroError` | If source file not found |
| `IOError`      | If file operations fail  |

Source code in `src/balatrobot/client.py`

```python
def prepare_save(self, source_path: str | Path) -> str:
    """Prepare a test save file for use with load_save.

    This copies a .jkr file from your test directory into Love2D's save directory
    in a temporary profile so it can be loaded with load_save().

    Args:
        source_path: Path to the .jkr save file to prepare

    Returns:
        The Love2D-relative path to use with load_save()
        (e.g., "checkpoint/save.jkr")

    Raises:
        BalatroError: If source file not found
        IOError: If file operations fail
    """
    source = Path(source_path)
    if not source.exists():
        raise BalatroError(
            f"Source save file not found: {source}", ErrorCode.MISSING_GAME_OBJECT
        )

    # Get save directory info
    save_info = self.get_save_info()
    if not save_info.get("save_directory"):
        raise BalatroError(
            "Cannot determine Love2D save directory", ErrorCode.INVALID_GAME_STATE
        )

    checkpoints_profile = "checkpoint"
    save_dir = Path(save_info["save_directory"])
    checkpoints_dir = save_dir / checkpoints_profile
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    # Copy the save file to the test profile
    dest_path = checkpoints_dir / "save.jkr"
    shutil.copy2(source, dest_path)

    # Return the Love2D-relative path
    return f"{checkpoints_profile}/save.jkr"

```

#### `save_checkpoint(checkpoint_name)`

Save the current save.jkr file as a checkpoint.

Parameters:

| Name              | Type  | Description | Default                                                                                                                                                                              |
| ----------------- | ----- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `checkpoint_name` | \`str | Path\`      | Either: - A checkpoint name (saved to checkpoints dir) - A full file path where the checkpoint should be saved - A directory path (checkpoint will be saved as 'save.jkr' inside it) |

Returns:

| Type   | Description                       |
| ------ | --------------------------------- |
| `Path` | Path to the saved checkpoint file |

Raises:

| Type           | Description                                               |
| -------------- | --------------------------------------------------------- |
| `BalatroError` | If no save file exists or the destination path is invalid |
| `IOError`      | If file operations fail                                   |

Source code in `src/balatrobot/client.py`

```python
def save_checkpoint(self, checkpoint_name: str | Path) -> Path:
    """Save the current save.jkr file as a checkpoint.

    Args:
        checkpoint_name: Either:
            - A checkpoint name (saved to checkpoints dir)
            - A full file path where the checkpoint should be saved
            - A directory path (checkpoint will be saved as 'save.jkr' inside it)

    Returns:
        Path to the saved checkpoint file

    Raises:
        BalatroError: If no save file exists or the destination path is invalid
        IOError: If file operations fail
    """
    # Get current save info
    save_info = self.get_save_info()
    if not save_info.get("save_exists"):
        raise BalatroError(
            "No save file exists to checkpoint", ErrorCode.INVALID_GAME_STATE
        )

    # Get the full save file path from API (already OS-specific)
    save_path = Path(save_info["save_file_path"])
    if not save_path.exists():
        raise BalatroError(
            f"Save file not found: {save_path}", ErrorCode.MISSING_GAME_OBJECT
        )

    # Normalize and interpret destination
    dest = Path(checkpoint_name).expanduser()
    # Treat paths without a .jkr suffix as directories
    if dest.suffix.lower() != ".jkr":
        raise BalatroError(
            f"Invalid checkpoint path provided: {dest}",
            ErrorCode.INVALID_PARAMETER,
            context={"path": str(dest), "reason": "Path does not end with .jkr"},
        )

    # Ensure destination directory exists
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise BalatroError(
            f"Invalid checkpoint path provided: {dest}",
            ErrorCode.INVALID_PARAMETER,
            context={"path": str(dest), "reason": str(e)},
        ) from e

    # Copy save file to checkpoint
    try:
        shutil.copy2(save_path, dest)
    except OSError as e:
        raise BalatroError(
            f"Failed to write checkpoint to: {dest}",
            ErrorCode.INVALID_PARAMETER,
            context={"path": str(dest), "reason": str(e)},
        ) from e

    return dest

```

#### `screenshot(path=None)`

Take a screenshot and save as both PNG and JPEG formats.

Parameters:

| Name   | Type   | Description | Default                                                                      |
| ------ | ------ | ----------- | ---------------------------------------------------------------------------- |
| `path` | \`Path | None\`      | Optional path for PNG file. If provided, PNG will be moved to this location. |

Returns:

| Type   | Description                                                              |
| ------ | ------------------------------------------------------------------------ |
| `Path` | Path to the PNG screenshot. JPEG is saved alongside with .jpg extension. |

Note

The response now includes both 'path' (PNG) and 'jpeg_path' (JPEG) keys. This method maintains backward compatibility by returning the PNG path.

Source code in `src/balatrobot/client.py`

```python
def screenshot(self, path: Path | None = None) -> Path:
    """
    Take a screenshot and save as both PNG and JPEG formats.

    Args:
        path: Optional path for PNG file. If provided, PNG will be moved to this location.

    Returns:
        Path to the PNG screenshot. JPEG is saved alongside with .jpg extension.

    Note:
        The response now includes both 'path' (PNG) and 'jpeg_path' (JPEG) keys.
        This method maintains backward compatibility by returning the PNG path.
    """
    screenshot_response = self.send_message("screenshot", {})

    if path is None:
        return Path(screenshot_response["path"])
    else:
        source_path = Path(screenshot_response["path"])
        dest_path = path
        shutil.move(source_path, dest_path)
        return dest_path

```

#### `send_message(name, arguments=None)`

Send JSON message to Balatro and receive response

Parameters:

| Name        | Type   | Description           | Default            |
| ----------- | ------ | --------------------- | ------------------ |
| `name`      | `str`  | Function name to call | *required*         |
| `arguments` | \`dict | None\`                | Function arguments |

Returns:

| Type   | Description                |
| ------ | -------------------------- |
| `dict` | Response from the game API |

Raises:

| Type                    | Description                  |
| ----------------------- | ---------------------------- |
| `ConnectionFailedError` | If not connected to the game |
| `BalatroError`          | If the API returns an error  |

Source code in `src/balatrobot/client.py`

```python
def send_message(self, name: str, arguments: dict | None = None) -> dict:
    """Send JSON message to Balatro and receive response

    Args:
        name: Function name to call
        arguments: Function arguments

    Returns:
        Response from the game API

    Raises:
        ConnectionFailedError: If not connected to the game
        BalatroError: If the API returns an error
    """
    if arguments is None:
        arguments = {}

    if not self._connected or not self._socket:
        raise ConnectionFailedError(
            "Not connected to the game API",
            error_code="E008",
            context={
                "connected": self._connected,
                "socket": self._socket is not None,
            },
        )

    # Create and validate request
    request = APIRequest(name=name, arguments=arguments)
    logger.debug(f"Sending API request: {name}")

    try:
        # Send request
        message = request.model_dump_json() + "\n"
        self._socket.send(message.encode())

        # Receive response using improved message handling
        complete_message = self._receive_complete_message()

        # Decode and validate the message
        message_str = complete_message.decode().strip()
        logger.debug(f"Raw message length: {len(message_str)} characters")
        logger.debug(f"Message preview: {message_str[:100]}...")

        # Ensure the message is properly formatted JSON
        if not message_str:
            raise BalatroError(
                "Empty response received from game",
                error_code="E001",
                context={"raw_data_length": len(complete_message)},
            )

        response_data = json.loads(message_str)

        # Check for error response
        if "error" in response_data:
            logger.error(f"API request {name} failed: {response_data.get('error')}")
            raise create_exception_from_error_response(response_data)

        logger.debug(f"API request {name} completed successfully")
        return response_data

    except socket.error as e:
        logger.error(f"Socket error during API request {name}: {e}")
        raise ConnectionFailedError(
            f"Socket error during communication: {e}",
            error_code="E008",
            context={"error": str(e)},
        ) from e
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response from API request {name}: {e}")
        logger.error(f"Problematic message content: {message_str[:200]}...")
        logger.error(
            f"Message buffer state: {len(self._message_buffer)} bytes remaining"
        )

        # Clear the message buffer to prevent cascading errors
        if self._message_buffer:
            logger.warning("Clearing message buffer due to JSON parse error")
            self._message_buffer = b""

        raise BalatroError(
            f"Invalid JSON response from game: {e}",
            error_code="E001",
            context={"error": str(e), "message_preview": message_str[:100]},
        ) from e

```

______________________________________________________________________

## Enums

### `balatrobot.enums.State`

Game state values representing different phases of gameplay in Balatro, from menu navigation to active card play and shop interactions.

Source code in `src/balatrobot/enums.py`

```python
@unique
class State(Enum):
    """Game state values representing different phases of gameplay in Balatro,
    from menu navigation to active card play and shop interactions."""

    SELECTING_HAND = 1
    HAND_PLAYED = 2
    DRAW_TO_HAND = 3
    GAME_OVER = 4
    SHOP = 5
    PLAY_TAROT = 6
    BLIND_SELECT = 7
    ROUND_EVAL = 8
    TAROT_PACK = 9
    PLANET_PACK = 10
    MENU = 11
    TUTORIAL = 12
    SPLASH = 13
    SANDBOX = 14
    SPECTRAL_PACK = 15
    DEMO_CTA = 16
    STANDARD_PACK = 17
    BUFFOON_PACK = 18
    NEW_ROUND = 19

```

### `balatrobot.enums.Actions`

Bot action values corresponding to user interactions available in different game states, from card play to shop purchases and inventory management.

Source code in `src/balatrobot/enums.py`

```python
@unique
class Actions(Enum):
    """Bot action values corresponding to user interactions available in
    different game states, from card play to shop purchases and inventory
    management."""

    SELECT_BLIND = 1
    SKIP_BLIND = 2
    PLAY_HAND = 3
    DISCARD_HAND = 4
    END_SHOP = 5
    REROLL_SHOP = 6
    BUY_CARD = 7
    BUY_VOUCHER = 8
    BUY_BOOSTER = 9
    SELECT_BOOSTER_CARD = 10
    SKIP_BOOSTER_PACK = 11
    SELL_JOKER = 12
    USE_CONSUMABLE = 13
    SELL_CONSUMABLE = 14
    REARRANGE_JOKERS = 15
    REARRANGE_CONSUMABLES = 16
    REARRANGE_HAND = 17
    PASS = 18
    START_RUN = 19
    SEND_GAMESTATE = 20

```

### `balatrobot.enums.Decks`

Starting deck types in Balatro, each providing unique starting conditions, card modifications, or special abilities that affect gameplay throughout the run.

Source code in `src/balatrobot/enums.py`

```python
@unique
class Decks(Enum):
    """Starting deck types in Balatro, each providing unique starting
    conditions, card modifications, or special abilities that affect gameplay
    throughout the run."""

    RED = "Red Deck"
    BLUE = "Blue Deck"
    YELLOW = "Yellow Deck"
    GREEN = "Green Deck"
    BLACK = "Black Deck"
    MAGIC = "Magic Deck"
    NEBULA = "Nebula Deck"
    GHOST = "Ghost Deck"
    ABANDONED = "Abandoned Deck"
    CHECKERED = "Checkered Deck"
    ZODIAC = "Zodiac Deck"
    PAINTED = "Painted Deck"
    ANAGLYPH = "Anaglyph Deck"
    PLASMA = "Plasma Deck"
    ERRATIC = "Erratic Deck"

```

### `balatrobot.enums.Stakes`

Difficulty stake levels in Balatro that increase game difficulty through various modifiers and restrictions, with higher stakes providing greater challenges and rewards.

Source code in `src/balatrobot/enums.py`

```python
@unique
class Stakes(Enum):
    """Difficulty stake levels in Balatro that increase game difficulty through
    various modifiers and restrictions, with higher stakes providing greater
    challenges and rewards."""

    WHITE = 1
    RED = 2
    GREEN = 3
    BLACK = 4
    BLUE = 5
    PURPLE = 6
    ORANGE = 7
    GOLD = 8

```

### `balatrobot.enums.ErrorCode`

Standardized error codes used in BalatroBot API that match those defined in src/lua/api.lua for consistent error handling across the entire system.

Source code in `src/balatrobot/enums.py`

```python
@unique
class ErrorCode(Enum):
    """Standardized error codes used in BalatroBot API that match those defined in src/lua/api.lua for consistent error handling across the entire system."""

    # Protocol errors (E001-E005)
    INVALID_JSON = "E001"
    MISSING_NAME = "E002"
    MISSING_ARGUMENTS = "E003"
    UNKNOWN_FUNCTION = "E004"
    INVALID_ARGUMENTS = "E005"

    # Network errors (E006-E008)
    SOCKET_CREATE_FAILED = "E006"
    SOCKET_BIND_FAILED = "E007"
    CONNECTION_FAILED = "E008"

    # Validation errors (E009-E012)
    INVALID_GAME_STATE = "E009"
    INVALID_PARAMETER = "E010"
    PARAMETER_OUT_OF_RANGE = "E011"
    MISSING_GAME_OBJECT = "E012"

    # Game logic errors (E013-E016)
    DECK_NOT_FOUND = "E013"
    INVALID_CARD_INDEX = "E014"
    NO_DISCARDS_LEFT = "E015"
    INVALID_ACTION = "E016"

```

______________________________________________________________________

## Exceptions

### Connection and Socket Errors

#### `balatrobot.exceptions.SocketCreateFailedError`

Socket creation failed (E006).

#### `balatrobot.exceptions.SocketBindFailedError`

Socket bind failed (E007).

#### `balatrobot.exceptions.ConnectionFailedError`

Connection failed (E008).

### Game State and Logic Errors

#### `balatrobot.exceptions.InvalidGameStateError`

Invalid game state for requested action (E009).

#### `balatrobot.exceptions.InvalidActionError`

Invalid action for current context (E016).

#### `balatrobot.exceptions.DeckNotFoundError`

Deck not found (E013).

#### `balatrobot.exceptions.InvalidCardIndexError`

Invalid card index (E014).

#### `balatrobot.exceptions.NoDiscardsLeftError`

No discards remaining (E015).

### API and Parameter Errors

#### `balatrobot.exceptions.InvalidJSONError`

Invalid JSON in request (E001).

#### `balatrobot.exceptions.MissingNameError`

Message missing required 'name' field (E002).

#### `balatrobot.exceptions.MissingArgumentsError`

Message missing required 'arguments' field (E003).

#### `balatrobot.exceptions.UnknownFunctionError`

Unknown function name (E004).

#### `balatrobot.exceptions.InvalidArgumentsError`

Invalid arguments provided (E005).

#### `balatrobot.exceptions.InvalidParameterError`

Invalid or missing required parameter (E010).

#### `balatrobot.exceptions.ParameterOutOfRangeError`

Parameter value out of valid range (E011).

#### `balatrobot.exceptions.MissingGameObjectError`

Required game object missing (E012).

______________________________________________________________________

## Models

The BalatroBot API uses Pydantic models to provide type-safe data structures that exactly match the game's internal state representation. All models inherit from `BalatroBaseModel` which provides consistent validation and serialization.

#### Base Model

#### `balatrobot.models.BalatroBaseModel`

Base model for all BalatroBot API models.

### Request Models

These models define the structure for specific API requests:

#### `balatrobot.models.StartRunRequest`

Request model for starting a new run.

#### `balatrobot.models.BlindActionRequest`

Request model for skip or select blind actions.

#### `balatrobot.models.HandActionRequest`

Request model for playing hand or discarding cards.

#### `balatrobot.models.ShopActionRequest`

Request model for shop actions.

### Game State Models

The game state models provide comprehensive access to all Balatro game information, structured hierarchically to match the Lua API:

#### Root Game State

#### `balatrobot.models.G`

Root game state response matching G in Lua types.

##### `state_enum`

Get the state as an enum value.

##### `convert_empty_list_to_none_for_hand(v)`

Convert empty list to None for hand field.

#### Game Information

#### `balatrobot.models.GGame`

Game state matching GGame in Lua types.

##### `convert_empty_list_to_dict(v)`

Convert empty list to empty dict.

##### `convert_empty_list_to_none(v)`

Convert empty list to None for optional nested objects.

#### `balatrobot.models.GGameCurrentRound`

Current round info matching GGameCurrentRound in Lua types.

##### `convert_empty_list_to_dict(v)`

Convert empty list to empty dict.

#### `balatrobot.models.GGameLastBlind`

Last blind info matching GGameLastBlind in Lua types.

#### `balatrobot.models.GGamePreviousRound`

Previous round info matching GGamePreviousRound in Lua types.

#### `balatrobot.models.GGameProbabilities`

Game probabilities matching GGameProbabilities in Lua types.

#### `balatrobot.models.GGamePseudorandom`

Pseudorandom data matching GGamePseudorandom in Lua types.

#### `balatrobot.models.GGameRoundBonus`

Round bonus matching GGameRoundBonus in Lua types.

#### `balatrobot.models.GGameRoundScores`

Round scores matching GGameRoundScores in Lua types.

#### `balatrobot.models.GGameSelectedBack`

Selected deck info matching GGameSelectedBack in Lua types.

#### `balatrobot.models.GGameShop`

Shop configuration matching GGameShop in Lua types.

#### `balatrobot.models.GGameStartingParams`

Starting parameters matching GGameStartingParams in Lua types.

#### `balatrobot.models.GGameTags`

Game tags model matching GGameTags in Lua types.

#### Hand Management

#### `balatrobot.models.GHand`

Hand structure matching GHand in Lua types.

#### `balatrobot.models.GHandCards`

Hand card matching GHandCards in Lua types.

#### `balatrobot.models.GHandCardsBase`

Hand card base properties matching GHandCardsBase in Lua types.

##### `convert_int_to_string(v)`

Convert integer values to strings.

#### `balatrobot.models.GHandCardsConfig`

Hand card configuration matching GHandCardsConfig in Lua types.

#### `balatrobot.models.GHandCardsConfigCard`

Hand card config card data matching GHandCardsConfigCard in Lua types.

#### `balatrobot.models.GHandConfig`

Hand configuration matching GHandConfig in Lua types.

#### Joker Information

#### `balatrobot.models.GJokersCards`

Joker card matching GJokersCards in Lua types.

#### `balatrobot.models.GJokersCardsConfig`

Joker card configuration matching GJokersCardsConfig in Lua types.

### Communication Models

These models handle the communication protocol between your bot and the game:

#### `balatrobot.models.APIRequest`

Model for API requests sent to the game.

#### `balatrobot.models.APIResponse`

Model for API responses from the game.

#### `balatrobot.models.ErrorResponse`

Model for API error responses matching Lua ErrorResponse.

#### `balatrobot.models.JSONLLogEntry`

Model for JSONL log entries that record game actions.

## Usage Examples

For practical implementation examples:

- Follow the [Developing Bots](https://coder.github.io/balatrobot/0.7.1/developing-bots/index.md) guide for complete bot setup
- Understand the underlying [Protocol API](https://coder.github.io/balatrobot/0.7.1/protocol-api/index.md) for advanced usage
- Reference the [Installation](https://coder.github.io/balatrobot/0.7.1/installation/index.md) guide for environment setup
