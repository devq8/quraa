/* Template Name: Upwind - Django Landing Template
   Author: Shreethemes
   Email: support@shreethemes.in
   Website: https://shreethemes.in
   Version: 2.0.0
   Created: March 2022
   File Description: Main JS file of the template
*/


/*********************************/
/*         INDEX                 */
/*================================
 *     01.  Preloader            *
 *     02.  Menus                *
 *     03.  Back to top          *
 *     04.  Dark & Light Mode    *
 *     05.  LTR & RTL Mode       *
 ================================*/
 window.addEventListener('load', fn, false)

 //  window.onload = function loader() {
 function fn() {
     // Preloader
     if (document.getElementById('preloader')) {
         setTimeout(() => {
             document.getElementById('preloader').style.visibility = 'hidden';
             document.getElementById('preloader').style.opacity = '0';
         }, 350);
     }
 }
/*********************/
/*     Menus         */
/*********************/

function windowScroll() {
    const navbar = document.getElementById("navbar");
    if (
        document.body.scrollTop >= 50 ||
        document.documentElement.scrollTop >= 50
    ) {
        navbar.classList.add("is-sticky");
    } else {
        navbar.classList.remove("is-sticky");
    }
}

window.addEventListener('scroll', (ev) => {
    ev.preventDefault();
    windowScroll();
})

// Navbar Active Class
try {
    var spy = new Gumshoe('#navbar-navlist a', {
        // Active classes
        // navClass: 'active', // applied to the nav list item
        // contentClass: 'active', // applied to the content
        offset: 80
    });
} catch (error) {
    
}


// Smooth scroll 
try {
    var scroll = new SmoothScroll('#navbar-navlist a', {
        speed: 800,
        offset: 80
    });
} catch (error) {
    
}

// Menu Collapse
const toggleCollapse = (elementId, show = true) => {
    const collapseEl = document.getElementById(elementId);
    if (show) {
        collapseEl.classList.remove('hidden');
    } else {
        collapseEl.classList.add('hidden');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Toggle target elements using [data-collapse]
    document.querySelectorAll('[data-collapse]').forEach(function (collapseToggleEl) {
        var collapseId = collapseToggleEl.getAttribute('data-collapse');

        collapseToggleEl.addEventListener('click', function () {
            toggleCollapse(collapseId, document.getElementById(collapseId).classList.contains('hidden'));
        });
    });

    // Close the collapsed (mobile) menu after a nav link is clicked
    document.querySelectorAll('#menu-collapse a.nav-link').forEach(function (linkEl) {
        linkEl.addEventListener('click', function () {
            toggleCollapse('menu-collapse', false);
        });
    });
});

window.toggleCollapse = toggleCollapse;

/*********************/
/*   Back To Top     */
/*********************/

window.onscroll = function () {
    scrollFunction();
};

function scrollFunction() {
    var mybutton = document.getElementById("back-to-top");
    if(mybutton!=null){
        if (document.body.scrollTop > 500 || document.documentElement.scrollTop > 500) {
            mybutton.classList.add("block");
            mybutton.classList.remove("hidden");
        } else {
            mybutton.classList.add("hidden");
            mybutton.classList.remove("block");
        }
    }
}

function topFunction() {
    document.body.scrollTop = 0;
    document.documentElement.scrollTop = 0;
}

/*********************/
/* Dark & Light Mode */
/*********************/
try {
    const htmlTag = document.getElementsByTagName("html")[0]
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)')
    const chk = document.getElementById('chk');

    function applyTheme(isDark){
        htmlTag.classList.toggle('dark', isDark)
        htmlTag.classList.toggle('light', !isDark)
        if (chk) chk.checked = isDark
    }

    // Follow the system preference by default.
    applyTheme(systemDark.matches)

    // React to system changes until the user manually overrides.
    let manualOverride = false
    systemDark.addEventListener('change', function (e) {
        if (!manualOverride) applyTheme(e.matches)
    })

    function changeTheme(e){
        e.preventDefault()
        manualOverride = true
        applyTheme(!htmlTag.classList.contains('dark'))
    }

    const switcher = document.getElementById("theme-mode")
    switcher?.addEventListener("click" ,changeTheme )

    chk?.addEventListener('change',changeTheme);
} catch (err) {

}


/*********************/
/* LTR & RTL Mode */
/*********************/
try{
    const htmlTag = document.getElementsByTagName("html")[0]
    function changeLayout(e){
        e.preventDefault()
        const switcherRtl = document.getElementById("switchRtl")
        if(switcherRtl.innerText === "LTR"){
            htmlTag.dir = "ltr"
        }
        else{
            htmlTag.dir = "rtl"
        }
        
    }
    const switcherRtl = document.getElementById("switchRtl")
    switcherRtl?.addEventListener("click" ,changeLayout )
}
catch(err){}


