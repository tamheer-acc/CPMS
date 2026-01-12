// ---------------------------
//          popoup js       
// ---------------------------

const params = "scrollbars=no,resizable=no,status=no,location=no,toolbar=no,menubar=no,width=400,height=300,left=100,top=100";

function openWindow(url){

    window.open(
        url,        //url to open
        "popupWindow",   //target: new window
        params      //features
    );
}


function openPopup(id){
    document.getElementById(id).classList.remove('hidden');
}


function closePopup(id){
    document.getElementById(id).classList.add('hidden');
}



// ---------------------------
//     js for update form      
// ---------------------------
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[data-edit="true"]').forEach(form => {
        form.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && e.target.tagName.toLowerCase() !== 'textarea') {
                e.preventDefault();
            }
        });
    });
});



// --------------------------------------
//       js for search & filter buttons    
// --------------------------------------
document.addEventListener("DOMContentLoaded", function() {

    // Detect which table exists
    const plansBody = document.getElementById("plansBody");
    const initiativesBody = document.getElementById("initiativesBody");
    const goalsBody = document.getElementById("goalsBody");
    const isPlansPage = !!plansBody;
    const isInitiativesPage = !!initiativesBody;
    const isPlanDetailsPage = !!goalsBody;

    // Shared elements
    const dropdownBtn = document.getElementById("dropdownDefaultButton");
    const dropdownMenu = document.getElementById("dropdown");
    const dropdownIcon = document.getElementById("dropdownIcon");
    const filterButtons = document.querySelectorAll(".filter-btn");
    const searchInput = document.getElementById("search");

    let currentFilter = ""; // either status or priority

    // Universal fetch function
    function fetchData(search = "", filter = "", page = 1) {
        let url = `?search=${encodeURIComponent(search)}&page=${page}`;

        if (isPlansPage) url += `&status=${filter}`;
        if (isInitiativesPage) url += `&priority=${filter}`;
        if (isPlanDetailsPage) url += `&status=${filter}`;

        fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(res => res.json())
            .then(data => {
                if (isPlansPage) plansBody.innerHTML = data.html;
                if (isInitiativesPage) initiativesBody.innerHTML = data.html;
                if (isPlanDetailsPage) goalsBody.innerHTML = data.html;
            });
    }

    // Dropdown toggle
    if (dropdownBtn) {
        dropdownBtn.addEventListener("click", e => {
            e.stopPropagation();
            dropdownMenu.classList.toggle("hidden");
            dropdownIcon.style.transform = dropdownMenu.classList.contains("hidden") ? "rotate(0deg)" : "rotate(180deg)";
        });
    }

    // Click outside to close
    document.addEventListener("click", () => {
        if (dropdownMenu) {
            dropdownMenu.classList.add("hidden");
            dropdownIcon.style.transform = "rotate(0deg)";
        }
    });

    if (dropdownMenu) dropdownMenu.addEventListener("click", e => e.stopPropagation());

    // Search input (auto fetch as user types)
    if (searchInput) {
        searchInput.addEventListener("input", () => {
            fetchData(searchInput.value, currentFilter);
        });
    }


    filterButtons.forEach(btn => {
        btn.addEventListener("click", function() {
            currentFilter = this.dataset.status || this.dataset.priority || "";
            fetchData(searchInput.value, currentFilter);
            if (dropdownMenu) {
                dropdownMenu.classList.add("hidden");
                dropdownIcon.style.transform = "rotate(0deg)";
            }
        });
    });

});



// ---------------------------
//  initiative page number js     
// ---------------------------
document.addEventListener('DOMContentLoaded', function(){
    const pageDropdownButton = document.getElementById('initiative-page-dropdown-button'); //button that has the word عدد الصفوف
    const pageDropdownIcon = document.getElementById('initiative-page-dropdown-icon'); //icon to be rotated
    const pageDropdown = document.getElementById('initiative-page-dropdown'); //the div to be not hidden
    const pageFilterButtons = document.querySelectorAll(".initiative-page-filter-btn");// buttons to be clicked an reload
    const pageDropdownText = document.getElementById('initiative-page-dropdown-text');
    const currentUrl = new URL(window.location.href);



    if (currentUrl.searchParams.get('per_page')){
        pageDropdownText.textContent = currentUrl.searchParams.get('per_page')
    }
    if (pageDropdownButton) {
        pageDropdownButton.addEventListener("click", e => {
            e.stopPropagation();
            pageDropdown.classList.toggle("hidden");
            pageDropdownIcon.style.transform = pageDropdown.classList.contains("hidden") ? "rotate(0deg)" : "rotate(180deg)";
        });
    }

    // Click outside to close
    document.addEventListener("click", () => {
        if (pageDropdown) {
            pageDropdown.classList.add("hidden");
            pageDropdownIcon.style.transform = "rotate(0deg)";
        }
    });

    if (pageDropdown) pageDropdown.addEventListener("click", e => e.stopPropagation());


    pageFilterButtons.forEach(btn => {
        btn.addEventListener("click", function() {
            const perPage = this.dataset.number;
            
            if (pageDropdown) {
                pageDropdown.classList.add("hidden");
                pageDropdownIcon.style.transform = "rotate(0deg)";
            }

            const url = new URL(window.location.href);
            url.searchParams.set("per_page", perPage);
            url.searchParams.set("page", 1); // reset to first page
            window.location.href = url.toString();
        });
    });

});



// ---------------------------
//      page number js (AJAX)
// ---------------------------
document.addEventListener('DOMContentLoaded', function () {

    const plansBody = document.getElementById("plansBody");
    const goalsBody = document.getElementById("goalsBody");
    const isPlansPage = !!plansBody;
    const isPlanDetailsPage = !!goalsBody;

    const pageDropdownButton = document.getElementById('page-dropdown-button');
    const pageDropdownIcon = document.getElementById('page-dropdown-icon');
    const pageDropdown = document.getElementById('page-dropdown');
    const pageFilterButtons = document.querySelectorAll(".page-filter-btn");
    const pageDropdownText = document.getElementById('page-dropdown-text');

    // toggle dropdown
    if (pageDropdownButton) {
        pageDropdownButton.addEventListener("click", e => {
            e.stopPropagation();
            pageDropdown.classList.toggle("hidden");
            pageDropdownIcon.style.transform =
                pageDropdown.classList.contains("hidden")
                    ? "rotate(0deg)"
                    : "rotate(180deg)";
        });
    }

    // click outside
    document.addEventListener("click", () => {
        if (pageDropdown) {
            pageDropdown.classList.add("hidden");
            pageDropdownIcon.style.transform = "rotate(0deg)";
        }
    });

    if (pageDropdown) {
        pageDropdown.addEventListener("click", e => e.stopPropagation());
    }

    // AJAX per_page
    pageFilterButtons.forEach(btn => {
        btn.addEventListener("click", function () {
            const perPage = this.dataset.number;

            // update dropdown text
            if (pageDropdownText) {
                pageDropdownText.textContent = perPage;
            }

            // close dropdown
            if (pageDropdown) {
                pageDropdown.classList.add("hidden");
                pageDropdownIcon.style.transform = "rotate(0deg)";
            }

            const url = new URL(window.location.href);
            url.searchParams.set("per_page", perPage);
            url.searchParams.set("page", 1);

            fetch(url, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
            .then(res => res.json())
            .then(data => {
                if (isPlansPage) plansBody.innerHTML = data.html;
                if (isPlanDetailsPage) goalsBody.innerHTML = data.html;
            });
        });
    });

});


// ---------------------------
//     confirm delete js     
// ---------------------------

function openDeleteModal(deleteUrl, message) {
    const modal = document.getElementById('deleteModal');
    const form  = document.getElementById('deleteModalForm');
    const text  = document.getElementById('deleteModalText');

    form.action = deleteUrl;
    text.textContent = message;
    modal.classList.remove('hidden');
}


function closeDeleteModal() {
    document.getElementById('deleteModal').classList.add('hidden');
}



// ---------------------------
//    assign employees js     
// ---------------------------

const toAdd = new Map();    
const toRemove = new Map(); 

document.querySelectorAll('.assign_employee_button').forEach(btn => { 
    btn.addEventListener('click', () => {
        openPopup('assign_employee');
    });
});


document.querySelectorAll('.add-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const li = btn.closest('li');
        const removeBtn = li.querySelector('.remove-btn');
        const id = btn.dataset.id;
        const name = li.querySelector('span').textContent;
        const wasAssigned = btn.dataset.assigned === 'true';

        if (!wasAssigned) {
            toAdd.set(id, name);
        }
        toRemove.delete(id);

        btn.disabled = true;
        removeBtn.disabled = false;
    });
});


document.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const li = btn.closest('li');
        const addBtn = li.querySelector('.add-btn');
        const id = btn.dataset.id;
        const name = li.querySelector('span').textContent;
        const wasAssigned = btn.dataset.assigned === 'true';

        if (wasAssigned) {
            toRemove.set(id, name);
        }
        toAdd.delete(id);

        btn.disabled = true;
        addBtn.disabled = false;
    });
});


document.getElementById('done-btn').addEventListener('click', () => {
    if (toAdd.size === 0 && toRemove.size === 0) {
        alert("لا توجد تغيرات");
        return;
    }

    let text = '';
    if (toAdd.size) text += 'تم تعيين: \n' + Array.from(toAdd.values()).join(', ') + '\n\n';
    if (toRemove.size) text += 'تم إلغاء تعيين: \n' + Array.from(toRemove.values()).join(', ');

    document.getElementById('popup-text').textContent = text;
    openPopup('confirm-popup');
});


document.getElementById('cancel-btn').addEventListener('click', () => {
    toAdd.clear();
    toRemove.clear();

    document.querySelectorAll('.add-btn').forEach(btn => {
        const wasAssigned = btn.dataset.assigned === 'true';
        btn.disabled = wasAssigned;
    });

    document.querySelectorAll('.remove-btn').forEach(btn => {
        const wasAssigned = btn.dataset.assigned === 'true';
        btn.disabled = !wasAssigned;
    });

    closePopup('assign_employee');
    closePopup('confirm-popup');
});


document.getElementById('confirmAssign').addEventListener('click', function() {
    const hiddenContainer = document.getElementById('hidden-inputs');
    hiddenContainer.innerHTML = ''; // clear inputs

    toAdd.forEach((name, id) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'to_add[]';
        input.value = id;  //id
        hiddenContainer.appendChild(input);
    });


    toRemove.forEach((name, id) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'to_remove[]';
        input.value = id;  
        hiddenContainer.appendChild(input);
    });

    document.getElementById('assignForm').submit();
});


function closeConfirmPopup() {
    closePopup('confirm-popup');
}


function closeAssignPopup() {
    closePopup('confirm-assign_employee');
}



// ---------------------------
//           KPI js     
// ---------------------------
document.addEventListener('DOMContentLoaded', () => {

    const addKpiBtn = document.getElementById('add_kpi_button')
    const title = document.getElementById('kpi-modal-title')
    const cancelKpiBtn = document.getElementById('cancel-btn-kpi')
    const form = document.getElementById('kpiForm');
    const initiativeId = addKpiBtn.dataset.initiativeId
    const initiativeTitle = addKpiBtn.dataset.initiativeTitle
    

    //  Add Kpi Button JS
    addKpiBtn.addEventListener('click', () => {
        form.reset(); // clear values
        form.kpi.value = null;
        form.unit.value = null;
        form.target_value.value = null;
        form.actual_value.value = null;

        form.removeAttribute('data-is-update');
        title.textContent = '  إضافة مؤشر أداء رئيسي لمبادرة' + initiativeTitle
        openPopup('kpi-modal');
    });

    // Edit Kpi Button JS
    document.querySelectorAll('.edit-kpi-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const kpiId = btn.dataset.kpiId;
            title.textContent = ' تعديل مؤشر ' + btn.dataset.kpiName
            form.action = `/initiatives/${initiativeId}/kpis/${kpiId}/update/`;
            form.dataset.isUpdate = "true"; // is update 

            form.kpi.value = btn.dataset.kpiName;
            form.unit.value = btn.dataset.unit;
            form.target_value.value = btn.dataset.target;
            form.actual_value.value = btn.dataset.actual;

            openPopup('kpi-modal');
        });
    });

    cancelKpiBtn.addEventListener('click', () => {

        closePopup('kpi-modal');
        form.reset();
    });
});
