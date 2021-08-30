# Thread Bot!

A bot purely to be our thread testing ground until d.py 2.0 is released fully.

Things this bot currently does:
 - Watches messages in the nomination voting channel and makes a thread on every message

# Local development

To setup your envrionment for local dev, you should do the follow:
 - Run `poetry install` to install the project dependancies & linters
 - Run `poetry run task precommit` to install the pre-commit hook

At any point, if you want to test your code conforms to the linter, you can run `poetry run task lint`

# Required Envrionment variables

The below env vars are available to be set in a `.env` file in the project's root directory.

 - `BOT_TOKEN` (required) - Your Discord bot token
 - `DEBUG` - `true` or `false` used to control debug mode (true by default)

# Config file

`config-default.yml` contains all of the default configuration that we use in production.

To run this bot locally, make a copy of this file and name it `config.yml`. Then change each ID to an ID that exists in your test server.

# Running the project

Once you have setup your `.env` and `config.yml` files, you can start the bot by running `docker-compose up` from the project's root directory.
