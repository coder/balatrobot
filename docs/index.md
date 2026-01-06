<style>
  .project-logos img {
    transition: transform 0.3s ease;
  }
  .project-logos img:hover {
    transform: scale(1.1);
  }
</style>

<div class="project-logos" style="display: flex; justify-content: center; align-items: flex-end; gap: 2rem; flex-wrap: wrap;">
  <figure style="text-align: center; margin: 0;">
    <a href="https://coder.github.io/balatrobot/">
      <img src="assets/balatrobot.svg" alt="BalatroBot" width="120">
    </a>
    <figcaption>
      <a href="https://coder.github.io/balatrobot/">BalatroBot</a><br>
      <small>API for developing Balatro bots</small>
    </figcaption>
  </figure>
  <figure style="text-align: center; margin: 0;">
    <a href="...">
      <img src="assets/balatrollm.svg" alt="BalatroLLM" width="80">
    </a>
    <figcaption>
      <a href="...">BalatroLLM</a><br>
      <small>Play Balatro with LLMs</small>
    </figcaption>
  </figure>
  <figure style="text-align: center; margin: 0;">
    <a href="...">
      <img src="assets/balatrobench.svg" alt="BalatroBench" width="80">
    </a>
    <figcaption>
      <a href="...">BalatroBench</a><br>
      <small>Benchmark LLMs playing Balatro</small>
    </figcaption>
  </figure>
</div>

---

BalatroBot is a mod for Balatro that serves a JSON-RPC 2.0 HTTP API, exposing game state and controls for external program interaction. The API provides endpoints for complete game control, including card selection, shop transactions, blind selection, and state management. External clients connect via HTTP POST to execute game actions programmatically.

!!! warning "Breaking Changes"

    **BalatroBot 1.0.0 introduces breaking changes:**

    - Now a CLI to start Balatro (no longer a Python client)
    - New JSON-RPC 2.0 protocol over HTTP/1.1
    - Updated endpoints and API structure
    - Removed game state logging functionality

    BalatroBot is now a Lua mod that exposes an API for programmatic game control.

<div class="grid cards" markdown>

- :material-download:{ .lg .middle } __Installation__

    ---

    Setup guide covering prerequisites and BalatroBot installation.

    [:octicons-arrow-right-24: Installation](installation.md)

- :material-robot:{ .lg .middle } __Example Bot__

    ---

    A minimal Python bot example to get started with BalatroBot.

    [:octicons-arrow-right-24: Example Bot](example-bot.md)

- :material-console:{ .lg .middle } __CLI Reference__

    ---

    Command-line interface for launching Balatro with BalatroBot.

    [:octicons-arrow-right-24: CLI Reference](cli.md)

- :material-file-document:{ .lg .middle } __BalatroBot API__

    ---

    Message formats, game states, methods, schema, enums and errors

    [:octicons-arrow-right-24: API Reference](api.md)

- :octicons-people-24:{ .lg .middle } __Contributing__

    ---

    Setup guide for developers, test suite, and contributing guidelines.

    [:octicons-arrow-right-24: Contributing](contributing.md)

- :octicons-sparkle-fill-16:{ .lg .middle } __Documentation for LLM__

    ---

    Docs in [llms.txt](https://llmstxt.org/) format. Paste the following link (or its content) into the LLM.

    [:octicons-arrow-right-24: llms-full.txt](llms-full.txt)

</div>
