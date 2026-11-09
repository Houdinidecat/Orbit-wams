'use strict';

(() => {
  const byId = (id) => document.getElementById(id);
  const form = byId('mission-form');
  const fields = ['nombre', 'destino', 'fecha', 'estado', 'notas'];
  const tbody = byId('records-body');
  const detailDialog = byId('detail-dialog');
  const deleteDialog = byId('delete-dialog');
  const dateFormatter = new Intl.DateTimeFormat('es-MX', { day: 'numeric', month: 'short', year: 'numeric' });
  const timeFormatter = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
  let records = [];
  let editingId = null;
  let mutationBusy = false;
  let listRequest = 0;
  let detailRequest = 0;
  let editRequest = 0;
  let pendingDelete = null;
  let detailId = null;
  const dialogOpeners = new WeakMap();

  class ApiError extends Error {
    constructor(message, status = 0, campos = {}) {
      super(message);
      this.status = status;
      this.campos = campos;
    }
  }

  async function api(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(path, {
        credentials: 'same-origin',
        ...options,
        signal: controller.signal,
        headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers }
      });
      let data;
      try { data = await response.json(); }
      catch { throw new ApiError('El servidor devolvió una respuesta inesperada. Inténtalo de nuevo.', response.status); }
      if (!response.ok) throw new ApiError(data.error || 'No se pudo completar la operación.', response.status, data.campos || {});
      return data;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error.name === 'AbortError') throw new ApiError('La solicitud tardó demasiado. Consulta la lista antes de volver a guardar para comprobar si se completó.');
      throw new ApiError('No se pudo conectar con Órbita. Verifica que el servidor esté activo y vuelve a intentarlo.');
    } finally { clearTimeout(timeout); }
  }

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function notify(message, type = 'success') {
    const feedback = byId('feedback');
    feedback.textContent = message;
    feedback.className = `feedback feedback-${type}`;
    feedback.hidden = false;
  }

  function formatDate(value) {
    if (!value) return 'Sin fecha';
    const date = new Date(`${value}T12:00:00`);
    return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
  }

  function formatTimestamp(value) {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : timeFormatter.format(date);
  }

  function statusBadge(status) {
    const suffix = status === 'En curso' ? ' status-progress' : status === 'Completada' ? ' status-done' : '';
    return node('span', `status-badge${suffix}`, status);
  }

  function renderRecords() {
    const fragment = document.createDocumentFragment();
    for (const mission of records) {
      const row = document.createElement('tr');
      const nameCell = document.createElement('td');
      nameCell.append(node('span', 'mission-id', `#${mission.id}`), node('span', 'mission-name', mission.nombre), node('span', 'mission-destination', mission.destino));
      const statusCell = document.createElement('td');
      statusCell.append(node('span', 'mission-date', formatDate(mission.fecha)), statusBadge(mission.estado));
      const actionCell = document.createElement('td');
      const actions = node('div', 'row-actions');
      for (const [action, label] of [['view', 'Ver'], ['edit', 'Editar'], ['delete', 'Eliminar']]) {
        const button = node('button', `row-control${action === 'delete' ? ' delete-action' : ''}`, label);
        button.type = 'button';
        button.dataset.action = action;
        button.dataset.id = String(mission.id);
        button.setAttribute('aria-label', `${label} misión ${mission.nombre}, ID ${mission.id}`);
        button.disabled = mutationBusy;
        actions.append(button);
      }
      actionCell.append(actions);
      row.append(nameCell, statusCell, actionCell);
      fragment.append(row);
    }
    tbody.replaceChildren(fragment);
    byId('record-count').textContent = String(records.length);
    byId('record-count').setAttribute('aria-label', `${records.length} ${records.length === 1 ? 'misión registrada' : 'misiones registradas'}`);
    byId('empty-records').hidden = records.length !== 0;
  }

  async function loadRecords() {
    const request = ++listRequest;
    byId('loading-records').hidden = false;
    byId('refresh-records').disabled = true;
    byId('records-body').setAttribute('aria-busy', 'true');
    try {
      const data = await api('/api/misiones');
      if (request !== listRequest) return;
      records = data.registros;
      renderRecords();
    } finally {
      if (request === listRequest) {
        byId('loading-records').hidden = true;
        byId('refresh-records').disabled = mutationBusy;
        byId('records-body').setAttribute('aria-busy', 'false');
      }
    }
  }

  function clearFieldErrors() {
    for (const field of fields) {
      byId(field).removeAttribute('aria-invalid');
      byId(field).setCustomValidity('');
      byId(`error-${field}`).textContent = '';
    }
  }

  function showFieldErrors(errors) {
    let first = null;
    for (const field of fields) {
      if (typeof errors[field] !== 'string') continue;
      byId(`error-${field}`).textContent = errors[field];
      byId(field).setAttribute('aria-invalid', 'true');
      if (!first) first = byId(field);
    }
    first?.focus();
  }

  function setMutationBusy(busy) {
    mutationBusy = busy;
    document.querySelectorAll('.registry-workspace button, .registry-workspace input, .registry-workspace select, .registry-workspace textarea, .mission-dialog button').forEach((control) => { control.disabled = busy; });
    form.setAttribute('aria-busy', String(busy));
    byId('save-mission').textContent = busy ? 'Guardando…' : editingId === null ? 'Agregar misión' : 'Guardar cambios';
    byId('confirm-delete').textContent = busy ? 'Eliminando…' : 'Eliminar misión';
  }

  function resetEditor({ focus = false } = {}) {
    editingId = null;
    ++editRequest;
    form.reset();
    clearFieldErrors();
    byId('editor-eyebrow').textContent = '01 — UNA NUEVA IDEA';
    byId('editor-title').textContent = 'Agregar registro';
    byId('editor-description').textContent = 'Completa los datos de tu misión. Los campos con * son obligatorios.';
    byId('save-mission').textContent = 'Agregar misión';
    byId('cancel-edit').hidden = true;
    if (focus) byId('nombre').focus();
  }

  async function refreshAfterMutation(message) {
    try {
      await loadRecords();
      notify(message);
    } catch (error) {
      notify(`${message} No se pudo actualizar la lista: ${error.message}`, 'warning');
    }
  }

  function openDialog(dialog, opener) {
    dialogOpeners.set(dialog, opener || document.activeElement);
    if (!dialog.open) dialog.showModal();
  }

  for (const dialog of [detailDialog, deleteDialog]) {
    dialog.addEventListener('close', () => {
      if (dialog === detailDialog) ++detailRequest;
      const opener = dialogOpeners.get(dialog);
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
      else byId('refresh-records').focus();
    });
    dialog.addEventListener('cancel', (event) => { if (mutationBusy) event.preventDefault(); });
  }

  function appendDetail(container, label, value, wide = false, className = '') {
    const group = node('div', wide ? 'detail-wide' : '');
    group.append(node('dt', '', label), node('dd', className, value));
    container.append(group);
  }

  async function viewMission(id, opener) {
    const request = ++detailRequest;
    detailId = null;
    byId('detail-title').textContent = `Misión #${id}`;
    byId('detail-content').replaceChildren(node('p', 'detail-loading', 'Consultando el registro…'));
    byId('detail-edit').hidden = true;
    openDialog(detailDialog, opener);
    byId('close-detail').focus();
    try {
      const data = await api(`/api/misiones/${id}`);
      if (!detailDialog.open || request !== detailRequest) return;
      const mission = data.registro;
      detailId = mission.id;
      const details = node('dl', 'detail-grid');
      appendDetail(details, 'Nombre de la misión', mission.nombre, true, 'detail-name');
      appendDetail(details, 'Destino', mission.destino);
      const state = node('div');
      const stateValue = node('dd');
      stateValue.append(statusBadge(mission.estado));
      state.append(node('dt', '', 'Estado'), stateValue);
      details.append(state);
      appendDetail(details, 'Fecha objetivo', formatDate(mission.fecha));
      appendDetail(details, 'ID del registro', `#${mission.id}`);
      appendDetail(details, 'Notas', mission.notas || 'Sin notas.', true);
      appendDetail(details, 'Creado', formatTimestamp(mission.creado_en));
      appendDetail(details, 'Última actualización', formatTimestamp(mission.actualizado_en));
      byId('detail-content').replaceChildren(details);
      byId('detail-edit').hidden = false;
    } catch (error) {
      if (detailDialog.open && request === detailRequest) {
        const message = node('p', 'detail-error', error.message);
        message.setAttribute('role', 'alert');
        byId('detail-content').replaceChildren(message);
      }
    }
  }

  async function editMission(id) {
    const request = ++editRequest;
    try {
      const data = await api(`/api/misiones/${id}`);
      if (request !== editRequest || mutationBusy) return;
      const mission = data.registro;
      clearFieldErrors();
      editingId = mission.id;
      for (const field of fields) byId(field).value = mission[field] || '';
      byId('editor-eyebrow').textContent = '01 — UN NUEVO RUMBO';
      byId('editor-title').textContent = `Editar registro #${mission.id}`;
      byId('editor-description').textContent = 'Actualiza los datos de esta misión y guarda los cambios.';
      byId('save-mission').textContent = 'Guardar cambios';
      byId('cancel-edit').hidden = false;
      byId('nombre').focus();
      notify(`Editando la misión #${mission.id}.`, 'info');
    } catch (error) {
      if (request === editRequest) notify(error.message, 'error');
    }
  }

  function askDelete(id, opener) {
    const mission = records.find((record) => record.id === id);
    if (!mission) return;
    pendingDelete = { id, nombre: mission.nombre };
    byId('delete-description').textContent = `Vas a eliminar “${mission.nombre}” (ID #${id}).`;
    byId('delete-error').hidden = true;
    byId('delete-error').textContent = '';
    openDialog(deleteDialog, opener);
    byId('cancel-delete').focus();
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (mutationBusy) return;
    clearFieldErrors();
    for (const field of ['nombre', 'destino']) {
      if (!byId(field).value.trim()) byId(field).setCustomValidity('Completa este campo.');
    }
    if (!form.reportValidity()) return;
    const payload = Object.fromEntries(fields.map((field) => [field, byId(field).value.trim()]));
    const targetId = editingId;
    let fieldErrors = null;
    ++editRequest;
    setMutationBusy(true);
    try {
      const data = await api(targetId === null ? '/api/misiones' : `/api/misiones/${targetId}`, { method: targetId === null ? 'POST' : 'PUT', body: JSON.stringify(payload) });
      const index = records.findIndex((record) => record.id === data.registro.id);
      if (index === -1) records.unshift(data.registro);
      else records[index] = data.registro;
      renderRecords();
      resetEditor();
      await refreshAfterMutation(targetId === null ? `Misión #${data.registro.id} agregada correctamente.` : `Misión #${data.registro.id} actualizada correctamente.`);
    } catch (error) {
      notify(error.message, 'error');
      fieldErrors = error.campos || {};
    } finally {
      setMutationBusy(false);
      if (fieldErrors) showFieldErrors(fieldErrors);
    }
  });

  for (const field of fields) {
    byId(field).addEventListener('input', () => {
      byId(field).setCustomValidity('');
      byId(field).removeAttribute('aria-invalid');
      byId(`error-${field}`).textContent = '';
    });
  }

  byId('cancel-edit').addEventListener('click', () => { resetEditor({ focus: true }); notify('Edición cancelada. Puedes agregar una nueva misión.', 'info'); });
  byId('empty-add').addEventListener('click', () => { resetEditor({ focus: true }); });
  byId('refresh-records').addEventListener('click', async () => {
    try { await loadRecords(); notify('Todos los registros están actualizados.', 'info'); }
    catch (error) { notify(error.message, 'error'); }
  });
  byId('lookup-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const input = byId('lookup-id');
    if (!input.reportValidity()) return;
    viewMission(Number(input.value), event.submitter);
  });
  tbody.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button || mutationBusy) return;
    const id = Number(button.dataset.id);
    if (button.dataset.action === 'view') viewMission(id, button);
    else if (button.dataset.action === 'edit') editMission(id);
    else if (button.dataset.action === 'delete') askDelete(id, button);
  });
  byId('close-detail').addEventListener('click', () => detailDialog.close());
  byId('detail-done').addEventListener('click', () => detailDialog.close());
  byId('detail-edit').addEventListener('click', () => { const id = detailId; detailDialog.close(); if (id !== null) editMission(id); });
  byId('cancel-delete').addEventListener('click', () => { pendingDelete = null; deleteDialog.close(); });
  byId('confirm-delete').addEventListener('click', async () => {
    if (!pendingDelete || mutationBusy) return;
    const mission = pendingDelete;
    let deleted = false;
    setMutationBusy(true);
    byId('delete-error').hidden = true;
    try {
      await api(`/api/misiones/${mission.id}`, { method: 'DELETE' });
      pendingDelete = null;
      deleted = true;
      records = records.filter((record) => record.id !== mission.id);
      if (editingId === mission.id) resetEditor();
      renderRecords();
      deleteDialog.close();
      await refreshAfterMutation(`Misión #${mission.id} eliminada correctamente.`);
    } catch (error) {
      byId('delete-error').textContent = error.message;
      byId('delete-error').hidden = false;
    } finally {
      setMutationBusy(false);
      if (deleted) byId('refresh-records').focus();
    }
  });

  loadRecords().catch((error) => notify(error.message, 'error'));
})();
