/**
 * once the DOM is loaded, 
 */
document.addEventListener('DOMContentLoaded', function() {

    // start of by showing a list of quizzes
    if (document.querySelector("#quiz-list")!=null){
        list_quizzes()
    }
});

/**
 * generate a chart using chart.js
 */
function list_quizzes() {
    
    // console.log("showing quizzes")

    // disable the other views
    document.querySelector("#quiz-list").style.display = "block";
    document.querySelector("#questions").style.display = "none";
    document.querySelector("#result").style.display = "none";
    

    document.querySelector("#headline").innerHTML = "Available Quizzes"
    
    fetch("list", {
        method: "POST"
    })
    .then((response) => {

        if (response.ok){
            response.json().then( data => {
                // console.log(data)
                quiz_list = document.querySelector("#quiz-list")

                for (const quiz of data.quizzes){
                    name_row = document.createElement("div")
                    name_row.classList.add("row", "p-2", "d-flex", "text-center")
                    name_row.innerHTML = "<h3>" + quiz.name + "</h3>"
                    quiz_list.append(name_row)

                    entry_row = document.createElement("div")
                    entry_row.classList.add("row", "bg-light")
                    quiz_list.append(entry_row)

                    entry_left = document.createElement("div")
                    entry_left.classList.add("col", "text-end")
                    entry_left.innerHTML = "Difficulty: " + "<strong>" + quiz.difficulty + "</strong>"
                    entry_row.append(entry_left)

                    if (data.logged_in) {
                        entry_middle = document.createElement("div")
                        entry_middle.classList.add("col", "text-center")
                        entry_middle.innerHTML = "result: " + Number((quiz.result.correct / quiz.result.number_of_questions)).toLocaleString(undefined,{style: 'percent', minimumFractionDigits:2})
                        entry_row.append(entry_middle)
    
                        entry_right = document.createElement("div")
                        entry_right.classList.add("col")
                        // <button type="button" class="btn btn-primary btn-sm">Small button</button>
                        button = document.createElement("button")
                        button.classList.add("btn", "btn-primary", "btn-sm")
                        button.setAttribute("type", "button")
                        button.setAttribute("onclick", `commence(${quiz.id})`)
                        button.innerHTML = "take"
                        entry_right.append(button)
                        entry_row.append(entry_right)
                    } else {
                        entry_right = document.createElement("div")
                        entry_right.classList.add("col")
                        // <a class="btn btn-primary" href="#" role="button">Link</a>
                        button = document.createElement("a")
                        button.classList.add("btn", "btn-primary", "btn-sm")
                        button.setAttribute("href", "login")
                        button.innerHTML = "log-in"
                        entry_right.append(button)
                        entry_row.append(entry_right)
                    }

                }
            })
        } else {
            response.json().then((data) => {
                alert(data.error)
            })
        }
    })
    .catch( error => {
        console.log('Error:', error);
    })
}