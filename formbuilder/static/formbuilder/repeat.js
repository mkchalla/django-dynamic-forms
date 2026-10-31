// Handles "Add another" / "Remove" for button-repeatable fields and
// sub-forms rendered by formbuilder.services.render_field().
//
// Each repeatable block is a `.repeat-container` with:
//   - data-base-name: the dotted path prefix shared by every instance
//   - data-next-index: the next integer index to hand out
//   - a `.repeat-items` element holding the visible `.repeat-item` blocks
//   - a `.repeat-template` <template> whose markup uses the literal
//     placeholder "__INDEX__" everywhere an instance index belongs
//   - a `.repeat-add` button and, per item, a `.repeat-remove` button
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".repeat-container").forEach(initRepeatContainer);
});

function initRepeatContainer(container) {
  const addButton = container.querySelector(".repeat-add");
  const itemsHost = container.querySelector(".repeat-items");
  const template = container.querySelector(".repeat-template");
  if (!addButton || !itemsHost || !template) return;

  addButton.addEventListener("click", function () {
    const nextIndex = parseInt(container.dataset.nextIndex || "1", 10);
    const html = template.innerHTML.split("__INDEX__").join(String(nextIndex));
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html.trim();
    const newItem = wrapper.firstElementChild;
    if (newItem) {
      itemsHost.appendChild(newItem);
      bindRemove(newItem);
    }
    container.dataset.nextIndex = String(nextIndex + 1);
  });

  itemsHost.querySelectorAll(".repeat-item").forEach(bindRemove);
}

function bindRemove(item) {
  const removeButton = item.querySelector(".repeat-remove");
  if (!removeButton) return;
  removeButton.addEventListener("click", function () {
    // Always leave at least one block so the field/sub-form is still
    // present in the submitted data (as an empty entry) if the user
    // removes every row they added.
    const host = item.parentElement;
    if (host && host.querySelectorAll(".repeat-item").length > 1) {
      item.remove();
    } else {
      item.querySelectorAll("input, textarea, select").forEach((el) => {
        if (el.type === "checkbox" || el.type === "radio") el.checked = false;
        else el.value = "";
      });
    }
  });
}
