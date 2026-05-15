"""
Contacts Routes Blueprint - Manages Persons, Organizations, and Groups
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, User, ContactPerson, ContactOrganization, ContactGroup, ContactGroupMember
from utils import log_audit

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('/settings/contacts', endpoint='contacts_settings')
@login_required
def contacts_settings():
    if not current_user.has_permission('settings_sections.contacts', 'view'):
        flash('No permission.', 'danger')
        return redirect(url_for('settings.settings'))

    persons = ContactPerson.query.order_by(ContactPerson.name).all()
    organizations = ContactOrganization.query.order_by(ContactOrganization.name).all()
    groups = ContactGroup.query.order_by(ContactGroup.name).all()
    users = User.query.filter_by(is_active=True).order_by(User.username).all()

    can_edit = current_user.has_permission('settings_sections.contacts', 'edit')
    can_delete = current_user.has_permission('settings_sections.contacts', 'delete')

    return render_template('contacts_settings.html',
                           persons=persons, organizations=organizations,
                           groups=groups, users=users,
                           can_edit=can_edit, can_delete=can_delete)


# ==================== PERSON CRUD ====================

@contacts_bp.route('/settings/contacts/person/add', endpoint='contact_person_add', methods=['POST'])
@login_required
def contact_person_add():
    if not current_user.has_permission('settings_sections.contacts', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    name = request.form.get('name', '').strip()[:256]
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    org_id = request.form.get('organization_id', type=int) or None
    person = ContactPerson(
        name=name,
        email=(request.form.get('email', '').strip() or None)[:256] if request.form.get('email', '').strip() else None,
        tel=(request.form.get('tel', '').strip() or None)[:64] if request.form.get('tel', '').strip() else None,
        organization_id=org_id
    )
    db.session.add(person)
    db.session.commit()
    log_audit(current_user.id, 'create', 'contact_person', person.id, f'Created contact person: {name}')
    flash(f'Person "{name}" added.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


@contacts_bp.route('/settings/contacts/person/<int:id>/edit', endpoint='contact_person_edit', methods=['POST'])
@login_required
def contact_person_edit(id):
    if not current_user.has_permission('settings_sections.contacts', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    p = ContactPerson.query.get_or_404(id)
    p.name = (request.form.get('name', p.name).strip() or p.name)[:256]
    p.email = (request.form.get('email', '').strip() or None)
    if p.email: p.email = p.email[:256]
    p.tel = (request.form.get('tel', '').strip() or None)
    if p.tel: p.tel = p.tel[:64]
    p.organization_id = request.form.get('organization_id', type=int) or None
    db.session.commit()
    log_audit(current_user.id, 'update', 'contact_person', p.id, f'Updated contact person: {p.name}')
    flash('Person updated.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


@contacts_bp.route('/settings/contacts/person/<int:id>/delete', endpoint='contact_person_delete', methods=['POST'])
@login_required
def contact_person_delete(id):
    if not current_user.has_permission('settings_sections.contacts', 'delete'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    p = ContactPerson.query.get_or_404(id)
    name = p.name
    db.session.delete(p)
    db.session.commit()
    log_audit(current_user.id, 'delete', 'contact_person', id, f'Deleted contact person: {name}')
    flash('Person deleted.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


# ==================== ORGANIZATION CRUD ====================

@contacts_bp.route('/settings/contacts/organization/add', endpoint='contact_org_add', methods=['POST'])
@login_required
def contact_org_add():
    if not current_user.has_permission('settings_sections.contacts', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    name = request.form.get('name', '').strip()[:256]
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    _e = request.form.get('email', '').strip()
    _t = request.form.get('tel', '').strip()
    _u = request.form.get('url', '').strip()
    _a = request.form.get('address', '').strip()
    _z = request.form.get('zip_code', '').strip()
    _i = request.form.get('info', '').strip()
    org = ContactOrganization(
        name=name,
        email=_e[:256] or None,
        tel=_t[:64] or None,
        url=_u[:512] or None,
        address=_a[:256] or None,
        zip_code=_z[:16] or None,
        info=_i[:512] or None
    )
    db.session.add(org)
    db.session.commit()
    log_audit(current_user.id, 'create', 'contact_org', org.id, f'Created organization: {name}')
    flash(f'Organization "{name}" added.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


@contacts_bp.route('/settings/contacts/organization/<int:id>/edit', endpoint='contact_org_edit', methods=['POST'])
@login_required
def contact_org_edit(id):
    if not current_user.has_permission('settings_sections.contacts', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    org = ContactOrganization.query.get_or_404(id)
    org.name = (request.form.get('name', org.name).strip() or org.name)[:256]
    org.email = (request.form.get('email', '').strip() or None)
    if org.email: org.email = org.email[:256]
    org.tel = (request.form.get('tel', '').strip() or None)
    if org.tel: org.tel = org.tel[:64]
    org.url = (request.form.get('url', '').strip() or None)
    if org.url: org.url = org.url[:512]
    org.address = (request.form.get('address', '').strip() or None)
    if org.address: org.address = org.address[:256]
    org.zip_code = (request.form.get('zip_code', '').strip() or None)
    if org.zip_code: org.zip_code = org.zip_code[:16]
    org.info = (request.form.get('info', '').strip() or None)
    if org.info: org.info = org.info[:512]
    db.session.commit()
    log_audit(current_user.id, 'update', 'contact_org', org.id, f'Updated organization: {org.name}')
    flash('Organization updated.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


@contacts_bp.route('/settings/contacts/organization/<int:id>/delete', endpoint='contact_org_delete', methods=['POST'])
@login_required
def contact_org_delete(id):
    if not current_user.has_permission('settings_sections.contacts', 'delete'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    org = ContactOrganization.query.get_or_404(id)
    name = org.name
    db.session.delete(org)
    db.session.commit()
    log_audit(current_user.id, 'delete', 'contact_org', id, f'Deleted organization: {name}')
    flash('Organization deleted.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


# ==================== GROUP CRUD ====================

@contacts_bp.route('/settings/contacts/group/add', endpoint='contact_group_add', methods=['POST'])
@login_required
def contact_group_add():
    if not current_user.has_permission('settings_sections.contacts', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    name = request.form.get('name', '').strip()[:256]
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    if ContactGroup.query.filter_by(name=name).first():
        flash('Group name already exists.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    _desc = request.form.get('description', '').strip()
    grp = ContactGroup(name=name, description=_desc[:512] or None)
    db.session.add(grp)
    db.session.commit()
    log_audit(current_user.id, 'create', 'contact_group', grp.id, f'Created contact group: {name}')
    flash(f'Group "{name}" created.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


@contacts_bp.route('/settings/contacts/group/<int:id>/edit', endpoint='contact_group_edit', methods=['POST'])
@login_required
def contact_group_edit(id):
    if not current_user.has_permission('settings_sections.contacts', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    grp = ContactGroup.query.get_or_404(id)
    new_name = (request.form.get('name', grp.name).strip() or grp.name)[:256]
    existing = ContactGroup.query.filter_by(name=new_name).first()
    if existing and existing.id != id:
        flash('Group name already exists.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    grp.name = new_name
    _desc = request.form.get('description', '').strip()
    grp.description = _desc[:512] or None
    db.session.commit()
    log_audit(current_user.id, 'update', 'contact_group', grp.id, f'Updated contact group: {grp.name}')
    flash('Group updated.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


@contacts_bp.route('/settings/contacts/group/<int:id>/delete', endpoint='contact_group_delete', methods=['POST'])
@login_required
def contact_group_delete(id):
    if not current_user.has_permission('settings_sections.contacts', 'delete'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    grp = ContactGroup.query.get_or_404(id)
    name = grp.name
    db.session.delete(grp)
    db.session.commit()
    log_audit(current_user.id, 'delete', 'contact_group', id, f'Deleted contact group: {name}')
    flash('Group deleted.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


@contacts_bp.route('/settings/contacts/group/<int:id>/add-member', endpoint='contact_group_add_member', methods=['POST'])
@login_required
def contact_group_add_member(id):
    if not current_user.has_permission('settings_sections.contacts', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    grp = ContactGroup.query.get_or_404(id)
    member_type = request.form.get('member_type', 'user')
    member_id = request.form.get('member_id', type=int)
    if not member_id:
        flash('Select a member.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))

    if member_type == 'user':
        if ContactGroupMember.query.filter_by(group_id=id, user_id=member_id).first():
            flash('User already in group.', 'warning')
            return redirect(url_for('contacts.contacts_settings'))
        m = ContactGroupMember(group_id=id, user_id=member_id)
    elif member_type == 'person':
        if ContactGroupMember.query.filter_by(group_id=id, person_id=member_id).first():
            flash('Person already in group.', 'warning')
            return redirect(url_for('contacts.contacts_settings'))
        m = ContactGroupMember(group_id=id, person_id=member_id)
    else:  # organization
        if ContactGroupMember.query.filter_by(group_id=id, organization_id=member_id).first():
            flash('Organization already in group.', 'warning')
            return redirect(url_for('contacts.contacts_settings'))
        m = ContactGroupMember(group_id=id, organization_id=member_id)

    db.session.add(m)
    db.session.commit()
    flash('Member added to group.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


@contacts_bp.route('/settings/contacts/group/member/<int:member_id>/remove', endpoint='contact_group_remove_member', methods=['POST'])
@login_required
def contact_group_remove_member(member_id):
    if not current_user.has_permission('settings_sections.contacts', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('contacts.contacts_settings'))
    m = ContactGroupMember.query.get_or_404(member_id)
    db.session.delete(m)
    db.session.commit()
    flash('Member removed.', 'success')
    return redirect(url_for('contacts.contacts_settings'))


# ==================== API (search for project form) ====================

@contacts_bp.route('/api/contacts/persons', endpoint='api_contacts_persons')
@login_required
def api_contacts_persons():
    q = request.args.get('q', '').strip()
    query = ContactPerson.query
    if q:
        query = query.filter(ContactPerson.name.ilike(f'%{q}%'))
    persons = query.order_by(ContactPerson.name).limit(50).all()
    result = []
    for p in persons:
        label = p.name
        if p.organization:
            label += f' ({p.organization.name})'
        if p.email:
            label += f' — {p.email}'
        result.append({'id': p.id, 'label': label, 'name': p.name,
                        'org': p.organization.name if p.organization else '',
                        'email': p.email or ''})
    return jsonify(result)


@contacts_bp.route('/api/contacts/organizations', endpoint='api_contacts_organizations')
@login_required
def api_contacts_organizations():
    q = request.args.get('q', '').strip()
    query = ContactOrganization.query
    if q:
        query = query.filter(ContactOrganization.name.ilike(f'%{q}%'))
    orgs = query.order_by(ContactOrganization.name).limit(50).all()
    result = []
    for o in orgs:
        label = o.name
        if o.email:
            label += f' — {o.email}'
        result.append({'id': o.id, 'label': label, 'name': o.name, 'email': o.email or ''})
    return jsonify(result)


@contacts_bp.route('/api/contacts/all', endpoint='api_contacts_all')
@login_required
def api_contacts_all():
    """Unified search across users, persons, organizations, and groups for lending contact picker."""
    q = request.args.get('q', '').strip().lower()
    results = []

    users = User.query.filter_by(is_active=True).order_by(User.username).all()
    for u in users:
        if not q or q in u.username.lower() or (u.email and q in u.email.lower()):
            results.append({'id': u.id, 'type': 'user', 'label': u.username, 'extra': u.email or ''})

    persons = ContactPerson.query.order_by(ContactPerson.name).all()
    for p in persons:
        if not q or q in p.name.lower() or (p.email and q in p.email.lower()):
            extra = p.organization.name if p.organization else (p.email or '')
            results.append({'id': p.id, 'type': 'person', 'label': p.name, 'extra': extra})

    orgs = ContactOrganization.query.order_by(ContactOrganization.name).all()
    for o in orgs:
        if not q or q in o.name.lower() or (o.email and q in o.email.lower()):
            results.append({'id': o.id, 'type': 'organization', 'label': o.name, 'extra': o.email or ''})

    groups = ContactGroup.query.order_by(ContactGroup.name).all()
    for g in groups:
        if not q or q in g.name.lower() or (g.description and q in g.description.lower()):
            results.append({'id': g.id, 'type': 'group', 'label': g.name, 'extra': g.description or ''})

    return jsonify(results[:60])
