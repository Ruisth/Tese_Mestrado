openssl req -x509 -newkey rsa:2048 -nodes -keyout /tmp/wrong.key -out /tmp/wrong.crt -days 1 -subj '/CN=wrong' 2>/dev/null
python -m egw_simulator run --scenario smoke --seed 42 --duration 10 --run-id itest-tls-wrongca-q1 --output ~/egw-tcg/itest --broker 127.0.0.1 --port 8883 --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD" --ca-cert /tmp/wrong.crt; echo "exit=$?"
