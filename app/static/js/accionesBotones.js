function clearSectionSearch() {
    const contenedorBusqueda = document.getElementById("search-section");
    const inputs = contenedorBusqueda.querySelectorAll("input[type='search'], input[type='number']");
    
    inputs.forEach(input => {
        input.value = ""; 
    });
    const checkboxes = contenedorBusqueda.querySelectorAll("input[type='checkbox']");
    checkboxes.forEach(checkbox => {
        checkbox.checked = false; 
    });
}
