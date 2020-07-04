const get_time = () => {
    var today = new Date();
    return today.getHours() + ":" + today.getMinutes() + ":" + today.getSeconds() + ":" + today.getMilliseconds();
}

const updateProjects = (user) => {
    projectList.innerHTML = "Loading projects..."

    // not using snapshot so that we can modify inline in the screen
    db.collection('projects').where("administrator_users." + user.uid, "==", true).get().then(snapshot => {
        const user_ids = new Set();
        const users = {};

        // create a unique set of all the created by user ids for all the projects
        snapshot.docs.forEach(project_doc => {
            const project_data = project_doc.data();
            user_ids.add(project_data.created_by_user_id);
            // administrator users are stored in a map of user id to boolean because firestore doesn't like
            // to use array contains in its rules, since it doesn't like arrays for concurrency, though
            // it does support arrays so what??
            Object.keys(project_data.administrator_users).forEach(key => user_ids.add(key));
        });

        if (Object.keys(snapshot.docs).length > 0) {
            // use the set to get the user information for them all
            const getUsersInfo = functions.httpsCallable('getUsersInfo');
            getUsersInfo({ user_ids: Array.from(user_ids).join(",") }).then(result => {
                setupProjects(snapshot.docs, result.data);
            });
        } else {
            projectList.innerHTML = "You have no projects. Click 'Create Project' to create one, or request to be added to one.";
        }
    }, err => {
        // this is what happens if you log out and you are still trying to access the database; this is fine,
        // so doing nothing
    });
}

// listen for auth status changes (user will be null if user logged out, an object if user logged in)
auth.onAuthStateChanged(user => {
    setupUI(user);

    if (user) {
        updateProjects(user);
    } else {
        setupProjects([]);
    }
})

// create projects
const createForm = document.querySelector('#create-form');
createForm.addEventListener('submit', (e) => {
    e.preventDefault();
    admin_users = {};
    admin_users[auth.currentUser.uid] = true;

    db.collection('projects').add({
        name: createForm['name'].value,
        created_by_user_id: auth.currentUser.uid,
        administrator_users: admin_users
    }).then(() => {
        const modal = document.querySelector('#modal-create');
        M.Modal.getInstance(modal).close();
        createForm.reset();
        updateProjects(auth.currentUser);
    }).catch(err => {
        console.log(err.message)
    });
})

// signup
const signupForm = document.querySelector('#signup-form');
signupForm.addEventListener('submit', (e) => {
    e.preventDefault();

    // get user info
    const email = signupForm['signup-email'].value;
    const password  = signupForm['signup-password'].value;
    const first_name = signupForm['signup-first-name'].value;
    const last_name = signupForm['signup-last-name'].value;

    // sign up
    auth.createUserWithEmailAndPassword(email, password).then( cred => {
        const addUserInfo = functions.httpsCallable('addUserInfo');
        return addUserInfo({ user_id: cred.user.uid, first_name: first_name, last_name: last_name });
    }).then(() => {
        const modal = document.querySelector('#modal-signup');
        M.Modal.getInstance(modal).close();
        signupForm.reset();
    });
})

// logout
const logout = document.querySelector('#logout');
logout.addEventListener('click', (e) => {
    e.preventDefault();
    auth.signOut().then( () => {
        // do nothing - changes are managed in onAuthStateChanged
    });
})

// login
const loginForm = document.querySelector('#login-form');
loginForm.addEventListener('submit', (e) => {
    e.preventDefault();

    const email = loginForm['login-email'].value;
    const password  = loginForm['login-password'].value;

    auth.signInWithEmailAndPassword(email, password).then( cred => {
        const modal = document.querySelector('#modal-login');
        M.Modal.getInstance(modal).close();
        loginForm.reset();
    });
});

// add administrator
const addAdministrator = ((caller, project_id) => {
    const email_format_error_message = "Please enter format xxx@domain.xxx";

    const input_box_html = `
        <form id="add_admin">
            <span class="input-field inline">
                <input id="add-administrator" type="email" class="validate">
                <span id="add-admin-error" class="helper-text" data-error=${email_format_error_message}>
                    Enter the email address of someone to add as another project administrator.
                </span>
            </span>
        </form>
    `;
    const admin_add_link_section = document.querySelector("#project_admin_add_link_" + project_id)
    admin_add_link_section.innerHTML = input_box_html;
    const addAdminEmailField = document.querySelector('#add-administrator');

    // response to submit
    const addAdminForm = document.querySelector('#add_admin');
    addAdminForm.addEventListener('submit', (e) => {
        e.preventDefault();

        auth.currentUser.getIdToken().then(token => {
            const addAdminToProject = functions.httpsCallable('addAdminToProject');
            addAdminToProject({email: addAdminEmailField.value,
                              project_id: project_id,
                              user_token: token}).then(result => {
                if (result.data.first_name) {
                    const adminListSpan = document.querySelector('#project_admins_' + project_id);
                    new_admin_html = createAdministratorEntry(false, project_id, result.data.user_id, result.data);
                    adminListSpan.innerHTML = adminListSpan.innerHTML + ", " + new_admin_html;
                    admin_add_link_section.innerHTML = `<a href="#" onclick=addAdministrator(this,'${project_id}')>Add</a></span>`
                } else {
                    const addAdminLabel = document.querySelector("#add-admin-error");
                    addAdminLabel.setAttribute("data-error", "Error: " + result.data.error);
                    addAdminEmailField.classList.add('invalid');

                    // If we don't react to changes the above weird error will stay inappropriately
                    function correctErrorMessage(e) {
                        const addAdminLabel = document.querySelector("#add-admin-error");
                        addAdminLabel.setAttribute("data-error", email_format_error_message);
                        // prevent this from firing every time and slowing things down
                        e.target.removeEventListener(e.type, arguments.callee);
                    }

                    addAdminEmailField.addEventListener('input', correctErrorMessage);
                }
            });
        });
    });

    // respond to focus loss
    addAdminEmailField.addEventListener('focusout', (field) => {
        if (addAdminEmailField.value === '') {
            // don't mess with hiding or anything, since user can select more than one
            field.target.parentNode.parentNode.parentNode.innerHTML = `<a href="#" onclick=addAdministrator(this,'${project_id}')>Add</a></span>`;
        }
    });

    // in case of a form submission error, reset the error field for email submissions
    addAdminEmailField.addEventListener('input', (field) => {
        const addAdminLabel = document.querySelector("#add-admin-error");
        addAdminLabel.setAttribute("data-error", email_format_error_message);
    })
});

// remove administrator
const removeAdministrator = ((caller, project_id, administrator_user_id) => {
     auth.currentUser.getIdToken().then(token => {
        const removeAdminFromProject = functions.httpsCallable('removeAdminFromProject');
        removeAdminFromProject({project_id: project_id,
                                administrator_user_id: administrator_user_id,
                                user_token: token}).then(result => {
            if (result.data.success) {
                if (administrator_user_id === auth.currentUser.uid) {
                    updateProjects(auth.currentUser);
                } else {
                    // find the span to remove and remove it
                    administrators_span = caller.parentNode.parentNode.parentNode;
                    remaining_spans = [].filter.call(administrators_span.childNodes, (element) => {
                       return element.nodeName.toLowerCase() === "span" // ignores comma text
                            && element.getAttribute("user_id") !== administrator_user_id; // removes removed span
                    });

                    administrators_span.innerHTML = remaining_spans.map((element) => { // converts to HTML
                        return element.outerHTML;
                    }).join(", "); // re-adds commas
                }
            } else {
                error_label = document.querySelector('#project-' + project_id + '-error-message');
                error_label.innerHTML = "Error: " + result.data.error;
                console.log(result.data)
            }
        });
     });
});