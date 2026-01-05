

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
document.querySelectorAll('.assign_employee_button').forEach(btn => { 
    btn.addEventListener('click', () => {
        document.getElementById('assign_employee').classList.remove('hidden');
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
