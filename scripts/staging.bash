#!/usr/bin/env bash

if ! command -v <the_command> &> /dev/null
then
    curl https://mise.run | sh
    echo 'eval "$(~/.local/bin/mise activate bash)"' >> ~/.bashrc
fi

mise install
mise x pdm sync
mise x pdm start
