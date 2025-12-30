
const params = `scrollbars=no,resizable=no,status=no,location=no,toolbar=no,menubar=no,width=400, height=300,left=100,top=100`;

function openPopup(url){

    window.open(
        url,        //url to open
        "_blank",   //target: new window
        params      //features

    );

}

