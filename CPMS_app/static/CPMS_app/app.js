

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
//        add KPI js     
// ---------------------------

document.getElementById('add_kpi_button').addEventListener('click', () => {
    openPopup('kpi-modal');
});


document.querySelectorAll('.edit-kpi-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const kpiId = btn.dataset.kpiId;
        const form = document.getElementById('kpiForm');
        const initiativeId = document.getElementById('add_kpi_button').dataset.initiativeId;

        form.action = `/initiatives/${initiativeId}/kpis/${kpiId}/update/`;
        form.dataset.isUpdate = "true"; // is update 

        form.kpi.value = btn.dataset.kpiName;
        form.unit.value = btn.dataset.unit;
        form.target_value.value = btn.dataset.target;
        form.actual_value.value = btn.dataset.actual;

        openPopup('kpi-modal');
    });
});


document.getElementById('cancel-btn-kpi').addEventListener('click', () => {
    const form  = document.getElementById('kpiForm');

    closePopup('kpi-modal');

    if (!form.dataset.isUpdate) { // reset the fields
        form.reset();
    }
});

