import pytest
from backend.app.models.models import Organization, Folder
from backend.app.repositories.base_repo import org_repo, folder_repo

def test_folder_hierarchy_and_cascade_delete(db):
    # 1. Create Organization
    org = org_repo.create(db, obj_in={"name": "Folder Test Org"})
    
    # 2. Create Root Folder
    root_folder = folder_repo.create(db, obj_in={
        "org_id": org.id,
        "name": "Root"
    })
    
    # 3. Create Subfolder under Root
    sub_folder = folder_repo.create(db, obj_in={
        "org_id": org.id,
        "parent_id": root_folder.id,
        "name": "Subfolder A"
    })

    # 4. Create Sub-subfolder under Subfolder
    sub_sub_folder = folder_repo.create(db, obj_in={
        "org_id": org.id,
        "parent_id": sub_folder.id,
        "name": "Sub-subfolder A1"
    })

    # 5. Assert parent-child relationships and tree retrieval
    db.refresh(root_folder)
    db.refresh(sub_folder)

    # Root has 1 child
    assert len(root_folder.subfolders) == 1
    assert root_folder.subfolders[0].id == sub_folder.id
    assert root_folder.subfolders[0].name == "Subfolder A"

    # Subfolder has 1 child
    assert len(sub_folder.subfolders) == 1
    assert sub_folder.subfolders[0].id == sub_sub_folder.id
    assert sub_folder.subfolders[0].name == "Sub-subfolder A1"

    # Sub-subfolder parent check
    assert sub_sub_folder.parent.id == sub_folder.id
    assert sub_sub_folder.parent.parent.id == root_folder.id

    # 6. Verify cascade delete: Deleting root_folder should delete subfolders recursively
    db.delete(root_folder)
    db.commit()

    # Query folder counts
    all_folders = db.query(Folder).filter(Folder.org_id == org.id).all()
    # All of them (Root, Sub, Sub-sub) should be gone because of ForeignKey cascade delete
    assert len(all_folders) == 0
