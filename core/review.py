"""Change tracking and approval gate for biographies.

Every save of a biography through the admin is recorded as a
:class:`~core.models.BiographyChange` holding a JSON snapshot of the
biography *before* and *after* the edit. Users who may approve changes
(``core.approve_biographychange``; superusers always can) have their edits
applied directly. Everyone else's edits are rolled back and kept as a
*pending* change until an approver applies it with :func:`approve`.

A snapshot covers the biography's own fields plus the related data edited
on the biography form: attributes, hometowns, teachers, students, sources
and transmission chains.
"""

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, gettext

from .models import (
    Attribute, Biography, BiographyChange, Esnad, EsnadLink, Location, Reading,
    Source, TeacherStudentRelationship,
)

APPROVE_PERMISSION = "core.approve_biographychange"

# Bookkeeping fields that are not part of the reviewed content.
_SKIP_FIELDS = {"id", "name_search", "created", "updated", "submitted_by", "last_modified_by"}

# Related collections stored in a snapshot, with their display labels.
RELATED_KEYS = {
    "attributes": _("Attributes"),
    "hometown": _("Hometowns"),
    "teachers": _("Notable Teachers"),
    "students": _("Notable Students"),
    "sources": _("Sources"),
    "esnads": _("Transmission Chains"),
}


def can_approve(user):
    """True if ``user``'s biography edits go live without review."""
    return bool(user and user.is_active and user.has_perm(APPROVE_PERMISSION))


def _scalar_fields():
    return [
        f for f in Biography._meta.concrete_fields
        if f.name not in _SKIP_FIELDS
    ]


def snapshot(bio):
    """Return a JSON-serializable dict describing ``bio`` as stored in the DB."""
    data = {}
    for f in _scalar_fields():
        value = getattr(bio, f.attname)
        if isinstance(f, models.FileField):
            value = value.name or ""
        data[f.name] = value

    data["attributes"] = sorted(bio.attributes.values_list("pk", flat=True))
    data["hometown"] = sorted(bio.hometown.values_list("pk", flat=True))

    def relations(**filters):
        qs = TeacherStudentRelationship.objects.filter(**filters).prefetch_related("notes")
        other = "teacher_id" if "student" in filters else "student_id"
        return sorted(
            [getattr(r, other), sorted(n.pk for n in r.notes.all())] for r in qs
        )

    data["teachers"] = relations(student=bio)
    data["students"] = relations(teacher=bio)
    data["sources"] = [
        [s.name_ar, s.name_en, s.link] for s in bio.sources.order_by("id")
    ]
    data["esnads"] = [
        list(e.links.order_by("order", "id").values_list("narrator_id", flat=True))
        for e in bio.esnads.order_by("id")
    ]
    return data


def _is_empty(value):
    return value in (None, "", [], False)


def changed_keys(before, after):
    """Keys whose value differs. For a new biography (empty ``before``) only
    non-empty values count as changes."""
    keys = []
    for key, value in after.items():
        if key in before:
            if before[key] != value:
                keys.append(key)
        elif not _is_empty(value):
            keys.append(key)
    return keys


def record(bio, action, before, after, user, status, label=None):
    """Store a change entry. Returns None when nothing changed on an update."""
    keys = changed_keys(before, after)
    if action == BiographyChange.Action.UPDATE and not keys:
        return None
    now = timezone.now()
    direct = status == BiographyChange.Status.DIRECT
    return BiographyChange.objects.create(
        biography=bio if action != BiographyChange.Action.DELETE else None,
        biography_label=(label or str(bio))[:300],
        action=action,
        status=status,
        before=before,
        after=after,
        changed_fields=keys,
        submitted_by=user,
        submitted_at=now,
        reviewed_by=user if direct else None,
        reviewed_at=now if direct else None,
    )


# --- applying an approved change -------------------------------------------

def _apply_relations(bio, rows, own_field, other_field):
    existing = {
        getattr(r, f"{other_field}_id"): r
        for r in TeacherStudentRelationship.objects.filter(**{own_field: bio})
    }
    valid_bios = set(Biography.objects.filter(pk__in=[r[0] for r in rows]).values_list("pk", flat=True))
    valid_notes = set(Reading.objects.values_list("pk", flat=True))
    wanted = set()
    for other_id, note_ids in rows:
        if other_id not in valid_bios or other_id == bio.pk:
            continue
        wanted.add(other_id)
        rel = existing.get(other_id)
        if rel is None:
            rel = TeacherStudentRelationship.objects.create(
                **{own_field: bio, f"{other_field}_id": other_id}
            )
        rel.notes.set([n for n in note_ids if n in valid_notes])
    for other_id, rel in existing.items():
        if other_id not in wanted:
            rel.delete()


def _apply_esnads(bio, chains):
    current = list(bio.esnads.order_by("id"))
    valid_bios = set(Biography.objects.values_list("pk", flat=True))
    for index, narrator_ids in enumerate(chains):
        esnad = current[index] if index < len(current) else Esnad.objects.create(biography=bio)
        esnad.links.all().delete()
        order = 0
        for narrator_id in narrator_ids:
            if narrator_id in valid_bios and narrator_id != bio.pk:
                order += 1
                EsnadLink.objects.create(esnad=esnad, narrator_id=narrator_id, order=order)
    for esnad in current[len(chains):]:
        esnad.delete()


def apply_snapshot(bio, data, keys):
    """Write the values of ``keys`` from snapshot ``data`` onto ``bio``."""
    scalars = {f.name: f for f in _scalar_fields()}
    for key in keys:
        field = scalars.get(key)
        if field is None:
            continue
        value = data.get(key)
        if field.is_relation and value is not None:
            if not field.related_model._default_manager.filter(pk=value).exists():
                value = None
        setattr(bio, field.attname, value)
    bio.save()

    if "attributes" in keys:
        bio.attributes.set(Attribute.objects.filter(pk__in=data["attributes"]))
    if "hometown" in keys:
        bio.hometown.set(Location.objects.filter(pk__in=data["hometown"]))
    if "teachers" in keys:
        _apply_relations(bio, data["teachers"], "student", "teacher")
    if "students" in keys:
        _apply_relations(bio, data["students"], "teacher", "student")
    if "sources" in keys:
        bio.sources.all().delete()
        Source.objects.bulk_create(
            Source(biography=bio, name_ar=a, name_en=e, link=link)
            for a, e, link in data["sources"]
        )
    if "esnads" in keys:
        _apply_esnads(bio, data["esnads"])


def conflicts(change):
    """Keys of a pending update whose live value changed since it was submitted."""
    if change.action != BiographyChange.Action.UPDATE or change.biography is None:
        return []
    current = snapshot(change.biography)
    return [
        k for k in change.changed_fields
        if current.get(k) != change.before.get(k) and current.get(k) != change.after.get(k)
    ]


def approve(change, user, note=""):
    """Apply a pending change. Returns False if it can no longer be applied."""
    with transaction.atomic():
        change = BiographyChange.objects.select_for_update().get(pk=change.pk)
        if change.status != BiographyChange.Status.PENDING or change.biography is None:
            return False
        bio = change.biography
        if change.action == BiographyChange.Action.CREATE:
            # The record already exists (unpublished); approval publishes it.
            bio.published = True
        else:
            apply_snapshot(bio, change.after, change.changed_fields)
        bio.last_modified_by = change.submitted_by
        bio.save()
        change.status = BiographyChange.Status.APPROVED
        change.reviewed_by = user
        change.reviewed_at = timezone.now()
        change.review_note = note
        change.save()
    return True


def reject(change, user, note=""):
    with transaction.atomic():
        change = BiographyChange.objects.select_for_update().get(pk=change.pk)
        if change.status != BiographyChange.Status.PENDING:
            return False
        change.status = BiographyChange.Status.REJECTED
        change.reviewed_by = user
        change.reviewed_at = timezone.now()
        change.review_note = note
        change.save()
    return True


# --- display ---------------------------------------------------------------

def field_label(key):
    if key in RELATED_KEYS:
        return RELATED_KEYS[key]
    try:
        return Biography._meta.get_field(key).verbose_name
    except Exception:
        return key


def _names(model, ids):
    objs = model._default_manager.in_bulk(ids)
    return [str(objs[i]) if i in objs else f"#{i} ({gettext('deleted')})" for i in ids]


def display_lines(key, value):
    """Human-readable lines for one snapshot value."""
    if value is None or value == "" or value == []:
        return []
    if key == "attributes":
        return _names(Attribute, value)
    if key == "hometown":
        return _names(Location, value)
    if key in ("teachers", "students"):
        bios = _names(Biography, [r[0] for r in value])
        lines = []
        for name, (_other, note_ids) in zip(bios, value):
            notes = ", ".join(_names(Reading, note_ids))
            lines.append(f"{name} ({notes})" if notes else name)
        return lines
    if key == "sources":
        return [" — ".join(p for p in (a, e, link) if p) for a, e, link in value]
    if key == "esnads":
        return [" ← ".join(_names(Biography, chain)) or "—" for chain in value]
    try:
        field = Biography._meta.get_field(key)
    except Exception:
        return [str(value)]
    if isinstance(value, bool):
        return [gettext("Yes") if value else gettext("No")]
    if field.is_relation:
        return _names(field.related_model, [value])
    return [str(value)]


def diff_rows(change, with_current=False):
    """Rows for the review/history tables: label plus before/after lines,
    each line flagged when it is not on the other side."""
    current = snapshot(change.biography) if with_current and change.biography else None
    conflict_keys = set(conflicts(change)) if current is not None else set()
    rows = []
    for key in change.changed_fields:
        before = display_lines(key, change.before.get(key))
        after = display_lines(key, change.after.get(key))
        row = {
            "key": key,
            "label": field_label(key),
            "before": [(line, line not in after) for line in before],
            "after": [(line, line not in before) for line in after],
            "conflict": key in conflict_keys,
        }
        if current is not None:
            row["current"] = display_lines(key, current.get(key))
        rows.append(row)
    return rows
