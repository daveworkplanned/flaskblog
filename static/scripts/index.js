const projectList = document.querySelector('.guides');
const loggedInLinks = document.querySelectorAll('.logged-in');
const loggedOutLinks = document.querySelectorAll('.logged-out');

const setupUI = (user) => {
    const loggedInDisplay = ((user) ? 'block' : 'none');
    const loggedOutDisplay = ((user) ? 'none' : 'block');

    loggedInLinks.forEach(link => link.style.display = loggedInDisplay);
    loggedOutLinks.forEach(link => link.style.display = loggedOutDisplay);
}

const createAdministratorEntry = (is_creator, project_id, administrator_user_id, administrator_user_data) => {
        admin_name = administrator_user_data.first_name + " " + administrator_user_data.last_name;

        let kill_link = "";

        if (!is_creator) {
            kill_link = `
            <a href="#" onclick=removeAdministrator(this,'${project_id}','${administrator_user_id}')><i class="material-icons" style="font-size: .9em">highlight_off</i></a>
            `;
        }
        return `<span user_id=${administrator_user_id}><span>${admin_name}</span><span>${kill_link}</span></span>`;
}

const paintAdministrators = (project_doc, user_data) => {
    project = project_doc.data();

    return Object.keys(project.administrator_users).map(administrator_user_id => {
        return createAdministratorEntry(administrator_user_id === project.created_by_user_id,
                                        project_doc.id,
                                        administrator_user_id,
                                        user_data[administrator_user_id]);
    }).join(", ")
}

const setupProjects = ((data, user_data) => {
    if (data.length) {
        let html = '';
        data.forEach(doc => {
            const project = doc.data();
            const created_by = user_data[project.created_by_user_id];

            const li = `
                <li>
                    <div class="collapsible-header grey lighten-4" style="display: block" onmouseenter="projectHeaderMouseEnter('${doc.id}');" onmouseleave="projectHeaderMouseLeave('${doc.id}');">
                        ${project.name}
                        <span style="float:right">
                            <a href="#" style="visibility: hidden; float: right" id="project_${doc.id}_delete_button")><i class="material-icons">highlight_off</i></a>
                        </span>
                    </div>
                    <div class="collapsible-body white">
                        Created by: ${created_by.first_name} ${created_by.last_name}<br />
                        Administrators: <span id="project_admins_${doc.id}">${paintAdministrators(doc, user_data)}</span>
                        <span id="project_admin_add_link_${doc.id}" style="padding-left: 15px;">
                            <a href="#" onclick=addAdministrator(this,'${doc.id}')>Add</a>
                        </span>
                        <div><span id="project-${doc.id}-error-message" class="red-text text-accent-4"></span></div>
                    </div>
                </li>
            `;
            html += li;
        });

        projectList.innerHTML = html;
     } else {
        projectList.innerHTML = '<h5 class="center-aligned">Log in to view projects</h5>'
     }
})

const projectHeaderMouseEnter = (project_id) => {
    document.querySelector('#project_' + project_id + '_delete_button').style.visibility = "visible";
}

const projectHeaderMouseLeave = (project_id) => {
    document.querySelector('#project_' + project_id + '_delete_button').style.visibility = "hidden";
}

// setup materialize components
document.addEventListener('DOMContentLoaded', function() {

  var modals = document.querySelectorAll('.modal');
  M.Modal.init(modals);

  var items = document.querySelectorAll('.collapsible');
  M.Collapsible.init(items);

});