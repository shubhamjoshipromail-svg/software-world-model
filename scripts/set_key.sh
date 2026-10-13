#!/bin/zsh
# Prompts for an OpenAI API key (hidden input), stores it in .env (chmod 600), never prints it.
ENV=~/software-world-model/.env
printf "Paste your OpenAI API key (input hidden), then press Enter: "
read -s KEY; echo
[ -z "$KEY" ] && { echo "No key entered. Nothing saved."; exit 1; }
touch "$ENV"; chmod 600 "$ENV"
grep -v '^OPENAI_API_KEY=' "$ENV" > "$ENV.tmp" 2>/dev/null; mv "$ENV.tmp" "$ENV"; chmod 600 "$ENV"
echo "OPENAI_API_KEY=$KEY" >> "$ENV"
grep -qx '.env' ~/software-world-model/.gitignore 2>/dev/null || echo '.env' >> ~/software-world-model/.gitignore
CODE=$(curl -s -o /dev/null -w '%{http_code}' https://api.openai.com/v1/models -H "Authorization: Bearer $KEY")
unset KEY
if [ "$CODE" = "200" ]; then echo "Saved. Key is valid (OpenAI responded 200). You can close this tab."; else echo "Saved, but OpenAI returned HTTP $CODE — key may be wrong. Re-run this script to replace it."; fi
