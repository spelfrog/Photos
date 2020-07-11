function increase_size() {
    set_size(parseInt(get_size()) - 1)
}

function decrease_size() {
    set_size(parseInt(get_size()) + 1)
}

function set_size(value) {
    document.documentElement.style
        .setProperty('--images-per-row', value);
}

function get_size() {
    return getComputedStyle(document.documentElement)
        .getPropertyValue('--images-per-row');
}
function show_only_favs() {
    $("#files").addClass("show-only-favs")
}
function show_all() {
    $("#files").removeClass("show-only-favs")
}
function set_fav() {
    let element = $(this)
    let fav = element.hasClass("fas")
    let file_element = element.parents(".file")
    let path = file_element.data("path")

    $.ajax("/fav", {
        data: {file:path, value: fav ? "false":"true"},
        success: function () {
            if(fav) {
                element.removeClass("fas").addClass("far")
                file_element.removeClass("fav")
            }else {
                element.addClass("fas").removeClass("far")
                file_element.addClass("fav")
            }
        },
        error: function (data) {
            alert(data)
            console.log(data)
        }
    })



}
function loadFolder(path) {
    let files = $('#files');
    let folders = $('#folders');
    $.ajax("/files",
        {
            url: "",
            data: {path: path},
            success: function (data) {
                $("#current-path").text(path)
                // clearing
                folders.html("")
                files.html("")
                // filling
                data['folders'].forEach(folder => {
                    folders.append(
                        $("<div>").addClass("folder").text(folder['name']).on("click", function () {
                            loadFolder(folder['path'])
                        })
                    )
                })
                data['files'].forEach(file => {
                    let orientation = file['meta']['Orientation']
                    let type = "other";
                    let fav = file['is_fav'] ? "fas" : "far"
                    let icons = $("<div>").addClass("overlay")

                    if (file['is_video']) {
                        type = "video"
                        icons.append(
                            // video length bubble
                            $("<div>").addClass("length").html(
                                "<i class=\"fas fa-fw fa-play\"></i> " +
                                Math.round(file['meta']['duration']*10)/10 + "s"
                            )
                        )
                    }else if (file['is_image'])
                        type = "image"

                    // fav / heard icon
                    icons.append(
                        $("<div>").addClass("fav").append(
                            $("<i class=\""+fav+" fa-heart\"></i>").on("click", set_fav)
                        )
                    )


                    files.append(
                        $("<div>").addClass("file").addClass( file['is_fav']?"fav":"").addClass("type-" + type).data("path", file['path']).append(
                            $("<img src='/image?preview=true&path=" + file['path'] + "'>")
                                .addClass("orientation-" + orientation)
                                .prop("title", file['name'] + "\n" + file['date'])
                        ).append(icons)
                    )
                })
            },
        });
}

$(document).ready(function () {
    loadFolder(".")
})