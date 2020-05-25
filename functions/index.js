const functions = require('firebase-functions');
const admin = require('firebase-admin');
const Knex = require('knex');
admin.initializeApp();
const firestore = admin.firestore();

// [START cloud_sql_postgres_knex_create]
// Initialize Knex, a Node.js SQL query builder library with built-in connection pooling.
const connect = () => {
  // Configure which instance and what database user to connect with.
  // Remember - storing secrets in plaintext is potentially unsafe. Consider using
  // something like https://cloud.google.com/kms/ to help keep secrets secret.
  const config = {
    user: functions.config().db_config.user, // e.g. 'my-user'
    password: functions.config().db_config.pw, // e.g. 'my-user-password'
    database: functions.config().db_config.database, // e.g. 'my-database'
  };

  config.host = functions.config().db_config.host;

  // Establish a connection to the database
  const knex = Knex({
    client: 'pg',
    connection: config,
  });

  // ... Specify additional properties here.
  // [START_EXCLUDE]

  // [START cloud_sql_postgres_knex_limit]
  // 'max' limits the total number of concurrent connections this pool will keep. Ideal
  // values for this setting are highly variable on app design, infrastructure, and database.
  knex.client.pool.max = 1;
  // 'min' is the minimum number of idle connections Knex maintains in the pool.
  // Additional connections will be established to meet this value unless the pool is full.
  knex.client.pool.min = 1;
  // [END cloud_sql_postgres_knex_limit]
  // [START cloud_sql_postgres_knex_timeout]
  // 'acquireTimeoutMillis' is the maximum number of milliseconds to wait for a connection checkout.
  // Any attempt to retrieve a connection from this pool that exceeds the set limit will throw an
  // SQLException.
  knex.client.pool.createTimeoutMillis = 30000; // 30 seconds
  // 'idleTimeoutMillis' is the maximum amount of time a connection can sit in the pool. Connections that
  // sit idle for this many milliseconds are retried if idleTimeoutMillis is exceeded.
  knex.client.pool.idleTimeoutMillis = 600000; // 10 minutes
  // [END cloud_sql_postgres_knex_timeout]
  // [START cloud_sql_postgres_knex_backoff]
  // 'createRetryIntervalMillis' is how long to idle after failed connection creation before trying again
  knex.client.pool.createRetryIntervalMillis = 200; // 0.2 seconds
  // [END cloud_sql_postgres_knex_backoff]
  // [START cloud_sql_postgres_knex_lifetime]
  // 'acquireTimeoutMillis' is the maximum possible lifetime of a connection in the pool. Connections that
  // live longer than this many milliseconds will be closed and reestablished between uses. This
  // value should be several minutes shorter than the database's timeout value to avoid unexpected
  // terminations.
  knex.client.pool.acquireTimeoutMillis = 600000; // 10 minutes
  // [START cloud_sql_postgres_knex_lifetime]

  // [END_EXCLUDE]
  return knex;
};

let knex_connector;

exports.getUsersInfo = functions.https.onCall((data, context) => {
    knex_connector = knex_connector || connect();

    return (async () => {
        // you have to do an await inside an async
        const records = await knex_connector.select('user_id', 'first_name', 'last_name')
            .from('pii_data.user_info')
            .whereIn('user_id', data["user_ids"].split(','))
            .then((rows) => {
                records_dict = {}

                rows.forEach((row) => {
                    records_dict[row.user_id] = {"first_name": row.first_name, "last_name": row.last_name}
                })

                if (Object.entries(records_dict).length === 0) {
                    records_dict = {"error": "no accounts with these ids exist"}
                }

                return records_dict;
            }).catch((error) => {
                console.error(error)

                return {"error": "technical error"}
            })

        return records;
    })();
});

exports.addUserInfo = functions.https.onCall((data, context) => {
    knex_connector = knex_connector || connect();

    return (async () => {
        // you have to do an await inside an async
        await knex_connector('pii_data.user_info')
            .insert({user_id: data["user_id"], first_name: data["first_name"], last_name: data["last_name"]});

        return {
            status: "success"
        }
    })();
});

function ValidationError(message) {
    this.name = 'ValidationError';
    this.message = message;
    this.stack = (new Error()).stack;
}
ValidationError.prototype = new Error;

// firebase access functions
exports.addAdminToProject = functions.https.onCall((data, context) => {
    return (async () => {
        let user_token = await admin.auth().verifyIdToken(data.user_token).catch((error) => {
            throw new ValidationError("user not logged in")
        });

        knex_connector = knex_connector || connect();

        // check to see if the logged in user is an administrator for this project
        const project_ref = await firestore.collection("projects").doc(data.project_id)
        const project_doc = await project_ref.get();

        if (!project_doc.exists) {
            throw new ValidationError("project id not found")
        }

        admin_users = project_doc.get("administrator_users") || {}; // allow for no admin users if bug

        if (!(user_token.uid in admin_users)) {
            throw new ValidationError("user does not have administrative rights to project")
        }

        const new_admin_user_record = await admin.auth().getUserByEmail(data.email).catch((error) => {
            throw new ValidationError("we couldn't find a user with that email address");
        });

        if (new_admin_user_record.uid in admin_users) {
            throw new ValidationError("user is already an administrator for this project")
        }

        // create dictionary entry to merge in
        new_admin_permission_rec = {}
        new_admin_permission_rec[new_admin_user_record.uid] = true;

        // merge in dictionary entry
        project_ref.set({
            "administrator_users": new_admin_permission_rec
        }, {merge: true});

        // Get user name information from other system
        const full_users = await knex_connector.select('first_name', 'last_name')
        .from('pii_data.user_info')
        .where({'user_id': new_admin_user_record.uid});

        return {
            first_name: full_users[0].first_name,
            last_name: full_users[0].last_name,
            user_id: new_admin_user_record.uid
        }
    })().catch((error) => {
        if (error instanceof ValidationError) {
            return {error: error.message}
        } else {
            throw error;
        }
    });
});

exports.removeAdminFromProject = functions.https.onCall((data, context) => {
    return (async () => {
        let user_token = await admin.auth().verifyIdToken(data.user_token).catch((error) => {
            throw new ValidationError("user not logged in")
        });

        knex_connector = knex_connector || connect();

        // check to see if the logged in user is an administrator for this project
        const project_ref = await firestore.collection("projects").doc(data.project_id)
        const project_doc = await project_ref.get();

        if (!project_doc.exists) {
            throw new ValidationError("project id not found")
        }

        admin_users = project_doc.get("administrator_users") || {}; // allow for no admin users if bug

        if (!(user_token.uid in admin_users)) {
            throw new ValidationError("user does not have administrative rights to project")
        }

        if (!(data.administrator_user_id in admin_users)) {
            throw new ValidationError("removed user is not an administrator for this project")
        }

        delete_map = {}
        delete_map[data.administrator_user_id] = admin.firestore.FieldValue.delete();

        await project_ref.set({ 'administrator_users' : delete_map}, { merge: true });

        return_map = {
            success: true
        }

        return_map["administrator_users"] = project_doc.administrator_users;

        return return_map
    })().catch((error) => {
        if (error instanceof ValidationError) {
            return {error: error.message}
        } else {
            throw error;
        }
    });
});