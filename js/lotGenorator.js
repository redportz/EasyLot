function CreateLot() {
    preventDefault();

    let lotName = document.getElementById("Lot-name")
    let folderName = document.getElementById("Folder-name")
    let url = document.getElementById("Url")

    AddLotToList(lotName, folderName, url)
    CreateFolder(folderName);
}

function AddLotToList(lotName, folderName, url) {
    
}

function CreateFolder(folderName) {
    
    CreatePolyFile()
    CreateSpotInfoFile()
}

function CreatePolyFile() {
    
}

function CreateSpotInfoFile() {
    
}