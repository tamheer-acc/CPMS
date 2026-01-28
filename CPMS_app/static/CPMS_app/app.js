// ---------------------------
//          popoup js       
// ---------------------------
function openWindow(url){
    const params = "scrollbars=no,resizable=no,status=no,location=no,toolbar=no,menubar=no,width=400,height=300,left=100,top=100";

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
    const logsBody = document.getElementById('logsBody')
    const isPlansPage = !!plansBody;
    const isInitiativesPage = !!initiativesBody;
    const isPlanDetailsPage = !!goalsBody;
    const isLogsBodyPage = !!logsBody;

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
        if (isLogsBodyPage) url += `&action=${filter}`;

        fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(res => res.json())
            .then(data => {
                if (isPlansPage) plansBody.innerHTML = data.html;
                if (isInitiativesPage) initiativesBody.innerHTML = data.html;
                if (isLogsBodyPage) logsBody.innerHTML = data.html;
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
            currentFilter = this.dataset.status || this.dataset.priority ||  this.dataset.action || "";
            fetchData(searchInput.value, currentFilter);
            if (dropdownMenu) {
                dropdownMenu.classList.add("hidden");
                dropdownIcon.style.transform = "rotate(0deg)";
            }
        });
    });

});







// ---------------------------
//    page number js (AJAX)
// ---------------------------
document.addEventListener('DOMContentLoaded', function () {

    const plansBody = document.getElementById("plansBody");
    const goalsBody = document.getElementById("goalsBody");
    const initiativesBody = document.getElementById("initiativesBody");
    const logsBody = document.getElementById('logsBody');
    const isPlansPage = !!plansBody;
    const isPlanDetailsPage = !!goalsBody;
    const isInitiativesPage = !!initiativesBody;
    const isLogsBodyPage = !!logsBody;

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

            if (isInitiativesPage) {
                // full reload
                window.location.href = url.toString(); 
            } 
            else {
                // AJAX 
                fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
                    .then(res => res.json())
                    .then(data => {
                        if (isPlansPage) plansBody.innerHTML = data.html;
                        if (isPlanDetailsPage) goalsBody.innerHTML = data.html;
                        if (isLogsBodyPage) logsBody.innerHTML = data.html;
                    });
            }

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
// assign reciver for note
// ---------------------------



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

const doneBtn = document.getElementById('done-btn');
if (doneBtn) {
    doneBtn.addEventListener('click', () => {
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
}


const cancelBtn = document.getElementById('cancel-btn');
if (cancelBtn) {

    cancelBtn.addEventListener('click', () => {
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
}


const confirmAssignBtn = document.getElementById('confirmAssign');
if (confirmAssignBtn){
    confirmAssignBtn.addEventListener('click', function() {
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
}


function closeConfirmPopup() {
    closePopup('confirm-popup');
}


function closeAssignPopup() {
    closePopup('confirm-assign_employee');
}



// ---------------------------
//           KPI js     
// ---------------------------
document.querySelectorAll('.edit-kpi-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.preventDefault(); // don't follow href

        const kpiId = btn.dataset.kpiId;
        const initiativeId = btn.dataset.initiativeId;

        const form = document.getElementById('kpiForm');
        const title = document.getElementById('kpi-modal-title');

        // Update modal title
        title.textContent = ' تعديل مؤشر ' + btn.dataset.kpiName;

        // Set form action to update URL
        form.action = '/initiatives/' + initiativeId + '/kpis/' + kpiId + '/edit/';

        // Pre-fill the form fields
        form.kpi.value = btn.dataset.kpiName;
        form.unit.value = btn.dataset.unit;
        form.target_value.valueAsNumber = parseFloat(btn.dataset.target) || 0;
        form.actual_value.valueAsNumber = parseFloat(btn.dataset.actual) || 0;

        // Mark form as update
        form.dataset.isUpdate = "true";

        // Show modal
        document.getElementById('kpi-modal').classList.remove('hidden');
        
    });


});

const addKpiBtn = document.getElementById('add_kpi_button');
if (addKpiBtn){
    addKpiBtn.addEventListener('click', () => {
        const form = document.getElementById('kpiForm');
        const title = document.getElementById('kpi-modal-title');

        form.reset(); // clear any old values from previous update
        delete form.dataset.isUpdate; // remove update flag
        title.textContent = 'إضافة مؤشر أداء رئيسي لمبادرة ' + addKpiBtn.dataset.initiativeTitle;

        // set form action to create KPI
        const initiativeId = addKpiBtn.dataset.initiativeId;
        form.action = '/initiatives/' + initiativeId + '/kpis/add/';

        // show modal
        document.getElementById('kpi-modal').classList.remove('hidden');
    });

}

const cancelBtnKpi = document.getElementById('cancel-btn-kpi')
if (cancelBtnKpi){
    document.getElementById('cancel-btn-kpi').addEventListener('click', () => {
        const form = document.getElementById('kpiForm');
        form.reset();
        document.getElementById('kpi-modal').classList.add('hidden');
    });

}



// ---------------------------
//     circle animation js     
// ---------------------------
window.addEventListener('load', () => {
    const gauge = document.getElementById('gauge');
    const gaugeText = document.getElementById('gauge-text');
    
    if (!gauge || !gaugeText) return;
    const targetValue = parseFloat(gauge.getAttribute('data-value')) || 0;
    const avg = parseInt(targetValue)*2

    gauge.setAttribute('stroke-dasharray', targetValue + ' 100');

    let current = 0;
    const step = avg / 50; // 50 frames ~ 1s
    const interval = setInterval(() => {
        current += step;
        if(current >= avg){
            current = avg;
            clearInterval(interval);
        }
        gaugeText.textContent = Math.round(current) + '%';
    }, 20);
});



// ---------------------------
//     add progress  js     
// ---------------------------
function addProgress(button) {
    const form = document.getElementById('userInitiativeForm');
    const progressInput = form.querySelector('.progress-input');

    const initiativeId = button.dataset.initiativeId;
    const currentProgress = button.dataset.currentProgress;

    form.action = '/initiatives/' + initiativeId + '/add_progress/';
    progressInput.value = currentProgress;

    openPopup('user-initiative-modal');
}

function closeProgressModal() {
    const form = document.getElementById('userInitiativeForm');
    form.reset();

    closePopup('user-initiative-modal')
}



// ---------------------------
//   message and navbar  js     
// ---------------------------
document.addEventListener("DOMContentLoaded", () => {
    setTimeout(() => {
        const container = document.getElementById("django-messages");
        if (container) {
            container.style.opacity = 0;
            setTimeout(() => container.remove(), 500);
        }
    }, 3000);

    
    // sidebar (navbar)
    // const btn = document.getElementById('toggle-nav');
    // const sidebar = document.getElementById('sidebar');

    // btn.addEventListener('click', () => {
    //     sidebar.classList.toggle('-translate-x-full');
    //     sidebar.classList.toggle('hidden'); // optional
    // });

});



// ---------------------------
//          charts js     
// ---------------------------

///////////// DONUT CHART \\\\\\\\\\\\\
function donutChart(labels, data, id){
    const canvas = document.getElementById(id);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                // backgroundColor: ['#CBD5E1', '#93C5FD', '#FCA5A5', '#86EFAC'],
                backgroundColor: ['#F2C75C', '#E59256', '#A13525', ' #00685E','#CBD5E1', '#93C5FD', '#FCA5A5', '#86EFAC'],
            }]
        },
        options: {
            plugins: {
                legend: { position: 'bottom', rtl: true }
            }
        }
    });

}



///////////////////////////////////////// BAR CHART \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
function barChart(labels, data, id, background='#AAC2BF', ticksDisplay=true, maxValue=null){
    const canvas = document.getElementById(id);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'bar',
            data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: background, 
                borderRadius: 4, 
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,  
            plugins: {
                legend: { display: false },
                tooltip:{ intersect: false } 
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ...(maxValue !== null && { max: maxValue }),
                    
                },               
                x:  {
                    ticks: {
                        display: ticksDisplay
                    },
                    grid: {
                        display: false
                    },
                }

            }
        }
    });
}                      




///////// STACKED BAR CHART \\\\\\\\\
function stackedBarChart(data, id) {
    const canvas = document.getElementById(id);
    if (!canvas || !data) return;

    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: data, 
        options: {
            indexAxis: 'y', 
            responsive: true,
            plugins: {
                tooltip: { mode: 'index', intersect: false },
                legend: { 
                    position: 'right',  // <- here you go
                    labels: {
                        boxWidth: 18,
                        boxHeight: 12,
                        padding: 12,
                        font: { size: 12 }
                    }
                }
            },
            scales: {
                x:  {
                    stacked: true,
                },

                y: { 
                    stacked: true, 
                    beginAtZero: true ,                     
                    grid: {
                        display: false
                    },
                }
            }
        }
    });
}



///////// LINE CHART \\\\\\\\\
function lineChart(data, id) {
    const canvas = document.getElementById(id);
    if (!canvas || !data) return;

    const ctx = canvas.getContext('2d');

    // formatted labels (DD/MM)
    const labels = data[Object.keys(data)[0]].map(d => {
        const date = new Date(d.date);
        return date.getDate() + '/' + (date.getMonth() + 1);
    });

    const colors = [
        '#F2C75C', '#E59256', '#A13525', '#00685E',
        '#8BAA99', '#006797', '#00A399', '#B98346'
    ];

    const datasets = Object.keys(data).map((dept, index) => ({
        label: dept,
        data: data[dept].map(d => d.avg),
        borderColor: colors[index % colors.length],
        backgroundColor: colors[index % colors.length],
        tension: 0.3,
        fill: false,
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2
    }));

    new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { 
                    position: 'bottom', 
                    rtl: true, 
                    labels: {
                        boxHeight: 12,
                        padding: 24,
                        boxWidth: 18,
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: { mode: 'index', intersect: false }
            },
            animation: {
                duration: 1500, // 1.5s
                easing: 'easeOutQuart'
            },
            transitions: {
                show: { animations: { x: { from: 0 }, y: { from: 0 } } },
                hide: { animations: { x: { to: 0 }, y: { to: 0 } } }
            },
            elements: {
                line: {
                    tension: 0.3 
                },
                point: {
                    radius: 3,
                    hoverRadius: 5
                }
            },
            scales: {
                y: { beginAtZero: true, max: 100 },
                x: {
                    ticks: { autoSkip: true, maxRotation: 45, minRotation: 0 },
                    grid: { display: false }
                }
            }
        }
    });
}



// donut chart labels and data
if (document.getElementById('donut-chart-labels')){
    const donutChartLabels = JSON.parse(document.getElementById('donut-chart-labels').textContent);
    const donutChartData = JSON.parse(document.getElementById('donut-chart-data').textContent);
    if (donutChartData && donutChartData.length > 0) {
        donutChart(donutChartLabels, donutChartData, 'donutChart');
    }  
}
// bar chart labels and data
if (document.getElementById('bar-chart-labels')){
    const barChartLabels = JSON.parse(document.getElementById('bar-chart-labels').textContent);
    const barChartData = JSON.parse(document.getElementById('bar-chart-data').textContent);
    if (barChartData && barChartData.length > 0) {
        barChart(barChartLabels, barChartData, 'barChart',background='#AAC2BF', ticksDisplay=true, maxValue=100);
    }
}
// bar chart labels and data
if (document.getElementById('bar-chart2-labels')){
    const barChartLabels2 = JSON.parse(document.getElementById('bar-chart2-labels').textContent);
    const barChartData2 = JSON.parse(document.getElementById('bar-chart2-data').textContent);
    if (barChartData2 && barChartData2.length > 0) {
        barChart(barChartLabels2, barChartData2, 'barChart2',['#00685E', '#55857F', '#AAC2BF', '#8BAA99'] ,false);
    }
}
// stacked bar chart data
if (document.getElementById('stacked-bar-chart-data')){
    const stackedChartData = JSON.parse(document.getElementById('stacked-bar-chart-data').textContent);
    if (stackedChartData && stackedChartData.labels.length > 0) {
        stackedBarChart(stackedChartData, 'stackedBarChart');
    }
}
// line chart labels and data
if (document.getElementById('line-chart-data')){
    const lineChartData = JSON.parse(document.getElementById('line-chart-data').textContent);
    if (lineChartData && Object.keys(lineChartData).length > 0) {
        lineChart(lineChartData, 'lineChart');
    }
}

// //====================== Plan Detail Dashboard =============================
// function GoalsInitiativesDonut(labels, goalsData, initiativesData, elementId) {
//     const donutCtx = document.getElementById(elementId);
//     if (!donutCtx) return;

//     new Chart(donutCtx, {
//         type: 'doughnut',
//         data: {
//             labels: labels,
//             datasets: [
//                 {
//                     label: 'الأهداف',
//                     data: { goalsData },
//                     backgroundColor: ['#F2C75C', '#E59256', '#A13525', ' #00685E'],
//                     borderWidth: 0,
//                     weight: 2
//                 },
//                 {
//                     label: 'المبادرات',
//                     data: { initiativesData },
//                     backgroundColor: ['#D1D5DB', '#93C5FD', '#6EE7B7', '#FCA5A5'],
//                     borderWidth: 0,
//                     weight: 1
//                 }
//             ]
//         },
//         options: {
//             cutout: '55%',
//             plugins: {
//                 legend: { position: 'right' }
//             }
//         }
//     });
// }
