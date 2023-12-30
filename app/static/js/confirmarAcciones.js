function confirmDeleteJob(id, project) {
    if (confirm("¿Estás seguro de que deseas eliminar este trabajo del proyecto "+project+"?")) {
        window.location.href = "/destroy-job/" + id; 
    }
}

function confirmDeleteUnit(id, unit) {
    if (confirm("¿Estás seguro de que deseas eliminar la unidad: "+unit+"?")) {
        window.location.href = "/destroy-unit/" + id; 
    }
}
