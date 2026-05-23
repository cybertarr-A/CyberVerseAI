import { apiRequest } from "../lib/api";

async function handleSubmit(){

    try{

        const response =
            await apiRequest(
                "/api/chat",
                {
                    method:"POST",

                    body:JSON.stringify({
                        message:"Hello"
                    })
                }
            );

        console.log(response);

    }catch(error){

        console.error(error);

    }
}
