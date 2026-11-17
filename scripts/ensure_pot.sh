N=clip-scout-pot
U=http://127.0.0.1:4416/ping
curl -s -m 2 "$U" >/dev/null && { echo "PO deja actif"; exit 0; }
docker info >/dev/null 2>&1 || { echo "Docker inactif : serveur PO non demarre"; exit 0; }
S=$(docker inspect -f '{{.State.Running}}' "$N" 2>/dev/null)
if [ "$S" = "true" ]; then
  echo "conteneur deja lance, attente du serveur"
elif [ "$S" = "false" ]; then
  docker start "$N" >/dev/null
else
  docker run -d --name "$N" --restart unless-stopped -m 512m -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider >/dev/null
fi
for i in $(seq 1 15); do
  curl -s -m 2 "$U" >/dev/null && { echo "PO actif"; exit 0; }
  sleep 2
done
echo "PO non joignable apres 30 s"
exit 0
