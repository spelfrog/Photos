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
    $("#files")
        .toggleClass("show-only-favs");
    updateFilterIcons();
}

function show_only_videos() {
    $("#files")
        .toggleClass("show-only-videos")
        .removeClass("show-only-images")
    updateFilterIcons();
}

function show_only_images() {
    $("#files")
        .toggleClass("show-only-images")
        .removeClass("show-only-videos")
    updateFilterIcons();
}

function updateFilterIcons() {
    let video = $(".video-filter").removeClass("active")
    let image = $(".image-filter").removeClass("active")
    let fav = $(".fav-filter").removeClass("active")

    let files = $("#files")


    if (files.hasClass("show-only-favs"))
        fav.addClass("active")

    if (files.hasClass("show-only-images")) {
        image.addClass("active")
    } else if (files.hasClass("show-only-videos")) {
        video.addClass("active")
    } else {
        image.addClass("active")
        video.addClass("active")
    }

    if (files.hasClass("show-only-favs"))
        fav.addClass("active")
}

function show_all() {
    $("#files")
        .removeClass("show-only-favs")
        .removeClass("show-only-images")
        .removeClass("show-only-videos")
    updateFilterIcons();
}

function set_fav() {
    let element = $(this)
    let fav = element.hasClass("fas")
    let file_element = element.parents(".file")
    let path = file_element.data("path")

    $.ajax("/fav", {
        data: {file: path, value: fav ? "false" : "true"},
        success: function () {
            if (fav) {
                element.removeClass("fas").addClass("far")
                file_element.removeClass("fav")
            } else {
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

function setPathDisplay(pathString) {
    let path = $("#current-path").html("")
    let folders = pathString.split("/")
    // root folder
    path.append(
        $("<span>").text("Root").addClass("folder-name")
            .on("click", () => loadFolder("."))
    )

    // rest of path
    folders.forEach((folder, index) => {
        if (folder === ".") return;
        path.append($("<span>").text(">").addClass("divider"))
        path.append($("<span>").text(folder).addClass("folder-name")
            .on("click", (data) => loadFolder(folders.slice(0, index + 1).join("/")))
        )
    })

    window.history.pushState({"path": pathString}, "", "?path=" + encodeURI(pathString));
}

window.onpopstate = function (e) {
    if (e.state) {
        loadFolder(e.state.path)
    }
};


function loadFolder(path) {
    let loading = $("#loading-indicator").addClass("active")
    let files = $('#files');
    let folders = $('#folders');
    $.ajax("/files",
        {
            url: "",
            data: {path: path},
            complete: function () {
                loading.removeClass("active")
            },
            success: function (data) {
                setPathDisplay(path)
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
                                Math.round(file['meta']['duration'] * 10) / 10 + "s"
                            )
                        )
                    } else if (file['is_image'])
                        type = "image"

                    // fav / heard icon
                    icons.append(
                        $("<div>").addClass("fav").append(
                            $("<i class=\"" + fav + " fa-heart\"></i>").on("click", set_fav)
                        )
                    )


                    files.append(
                        $("<div>").addClass("file").addClass(file['is_fav'] ? "fav" : "").addClass("type-" + type).data("path", file['path']).append(
                            $("<img src='/image?preview=true&path=" + file['path'] + "'>")
                                .addClass("orientation-" + orientation)
                                .prop("title", file['name'] + "\n" + file['date'])
                        ).append(icons)
                    )
                })
            },
        });
}

function get_url_parameter(param) {
    let key_value_pairs = window.location.search.substring(1).split('&');
    for (let i = 0; i < key_value_pairs.length; i++) {
        let key_value = key_value_pairs[i].split('=');
        if (key_value[0] === param)
            return decodeURI(key_value[1]);
    }
}

$(document).ready(function () {
    let path = get_url_parameter("path") || "."
    loadFolder(path)
    updateFilterIcons();
})