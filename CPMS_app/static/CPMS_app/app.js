// ---------------------------
//       open popoup js       
// ---------------------------
const params = "scrollbars=no,resizable=no,status=no,location=no,toolbar=no,menubar=no,width=400,height=300,left=100,top=100";

function openPopup(url){

    window.open(
        url,        //url to open
        "popupWindow",   //target: new window
        params      //features

    );

}

// ---------------------------
//       assign emp btn js       
// ---------------------------
document.querySelectorAll('.assign_employee_button').forEach(btn => { 
    btn.addEventListener('click', () => {
        document.getElementById('assign_employee').classList.remove('hidden');
    });
});

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
    const dropdownBtn = document.getElementById("dropdownDefaultButton");
    const dropdownMenu = document.getElementById("dropdown");
    const dropdownIcon = document.getElementById("dropdownIcon");
    const filterButtons = document.querySelectorAll(".filter-btn");
    const searchInput = document.getElementById("search");
    const plansBody = document.getElementById("plansBody");

    let currentStatus = "";

    function fetchPlans(search='', status='', page=1) {
        const url = `?search=${encodeURIComponent(search)}&status=${status}&page=${page}`;
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(res => res.json())
        .then(data => {
            plansBody.innerHTML = data.html;
        });
    }

    // Dropdown toggle
    dropdownBtn.addEventListener("click", e => {
        e.stopPropagation();
        dropdownMenu.classList.toggle("hidden");
        dropdownIcon.style.transform = dropdownMenu.classList.contains("hidden") ? "rotate(0deg)" : "rotate(180deg)";
    });
    document.addEventListener("click", () => {
        dropdownMenu.classList.add("hidden");
        dropdownIcon.style.transform = "rotate(0deg)";
    });
    dropdownMenu.addEventListener("click", e => e.stopPropagation());

    // Search input event
    searchInput.addEventListener("input", () => {
        fetchPlans(searchInput.value, currentStatus);
    });

    // Filter buttons
    filterButtons.forEach(btn => {
        btn.addEventListener("click", function() {
            currentStatus = this.dataset.status;
            fetchPlans(searchInput.value, currentStatus);
            dropdownMenu.classList.add("hidden");
            dropdownIcon.style.transform = "rotate(0deg)";
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
const toAdd = new Map();    // using map to get emp name not just id
const toRemove = new Map(); 

// toggling buttons
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



// popup
document.getElementById('done-btn').addEventListener('click', () => {
    if (toAdd.size === 0 && toRemove.size === 0) {
        alert("لا توجد تغيرات");
        return;
    }

    let text = '';
    if (toAdd.size) text += 'تم تعيين: \n' + Array.from(toAdd.values()).join(', ') + '\n\n';
    if (toRemove.size) text += 'تم إلغاء تعيين: \n' + Array.from(toRemove.values()).join(', ');

    document.getElementById('popup-text').textContent = text;
    document.getElementById('confirm-popup').classList.remove('hidden');
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

    document.getElementById('assign_employee').classList.add('hidden');
    document.getElementById('confirm-popup').classList.add('hidden'); // hide confirm too
});


// emp IDs 
document.getElementById('confirmAssign').addEventListener('click', function() {
    const hiddenContainer = document.getElementById('hidden-inputs');
    hiddenContainer.innerHTML = ''; // clear previous inputs

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
        input.value = id;  //  did
        hiddenContainer.appendChild(input);
    });

    document.getElementById('assignForm').submit();
});



function closePopup() {
    document.getElementById('confirm-popup').classList.add('hidden');
}

function closeAssignPopup() {
    document.getElementById('assign_employee').classList.add('hidden');
}
