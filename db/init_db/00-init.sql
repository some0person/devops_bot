SELECT pg_create_physical_replication_slot('replication_slot');

CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL
);

CREATE TABLE phone_nums (
    id SERIAL PRIMARY KEY,
    phone_num VARCHAR NOT NULL
);
