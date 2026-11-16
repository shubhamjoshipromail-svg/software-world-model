# Security

The benchmark runs third-party business apps in Docker and lets a model drive a browser against them. It is
built to stay on your machine: every port binds to `127.0.0.1`, agents cannot navigate to other hosts, and mail
is disabled. Do not expose these containers to a network, and do not point the harness at a real instance of
any of these apps.

Credentials in `envs/*/.env` are generated locally by `swm up` and are only meaningful on your machine.

If you find a way for an episode to reach outside localhost, or any other security problem, please report it
privately through GitHub's "Report a vulnerability" button on this repository rather than a public issue.
