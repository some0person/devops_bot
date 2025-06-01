#!/bin/bash
set -e

echo "host replication $DB_REPL_USER all trust" | tee -a /var/lib/postgresql/data/pg_hba.conf
echo "host $DB_DATABASE $DB_USER all scram-sha-256" | tee -a /var/lib/postgresql/data/pg_hba.conf
echo "host $DB_DATABASE $DB_REPL_USER all scram-sha-256" | tee -a /var/lib/postgresql/data/pg_hba.conf

psql -v ON_ERROR_STOP=1 --username "$DB_USER" --dbname "$DB_DATABASE" <<-EOSQL
	CREATE USER $DB_REPL_USER WITH REPLICATION ENCRYPTED PASSWORD '$DB_REPL_PASSWORD';
EOSQL
